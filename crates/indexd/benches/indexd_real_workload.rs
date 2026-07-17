use std::alloc::{GlobalAlloc, Layout, System};
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{bail, Context, Result};
use axum::body::{Body, Bytes};
use axum::http::{Request, Response, StatusCode};
use axum::Router;
use indexd::{api, AppState};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::sync::Barrier;
use tower::ServiceExt;

const REPORT_SCHEMA: &str = "indexd-real-workload-benchmark-v1";
const NAMESPACE: &str = "code";
const RESPONSE_LIMIT_BYTES: usize = 4 * 1024 * 1024;
const MIN_RATIO_BASELINE_NS: f64 = 1_000.0;

struct CountingAllocator;

static ALLOCATION_COUNT: AtomicU64 = AtomicU64::new(0);
static ALLOCATED_BYTES: AtomicU64 = AtomicU64::new(0);

unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let pointer = unsafe { System.alloc(layout) };
        if !pointer.is_null() {
            ALLOCATION_COUNT.fetch_add(1, Ordering::Relaxed);
            ALLOCATED_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        }
        pointer
    }

    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        let pointer = unsafe { System.alloc_zeroed(layout) };
        if !pointer.is_null() {
            ALLOCATION_COUNT.fetch_add(1, Ordering::Relaxed);
            ALLOCATED_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        }
        pointer
    }

    unsafe fn dealloc(&self, pointer: *mut u8, layout: Layout) {
        unsafe { System.dealloc(pointer, layout) };
    }

    unsafe fn realloc(&self, pointer: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        let replacement = unsafe { System.realloc(pointer, layout, new_size) };
        if !replacement.is_null() {
            ALLOCATION_COUNT.fetch_add(1, Ordering::Relaxed);
            ALLOCATED_BYTES.fetch_add(new_size as u64, Ordering::Relaxed);
        }
        replacement
    }
}

#[global_allocator]
static GLOBAL_ALLOCATOR: CountingAllocator = CountingAllocator;

#[derive(Clone, Copy)]
struct AllocationSnapshot {
    count: u64,
    bytes: u64,
}

impl AllocationSnapshot {
    fn capture() -> Self {
        Self {
            count: ALLOCATION_COUNT.load(Ordering::Relaxed),
            bytes: ALLOCATED_BYTES.load(Ordering::Relaxed),
        }
    }

    fn delta(self, before: Self) -> Self {
        Self {
            count: self.count.saturating_sub(before.count),
            bytes: self.bytes.saturating_sub(before.bytes),
        }
    }
}

#[derive(Debug)]
struct Options {
    profile: String,
    output: Option<PathBuf>,
    baseline: Option<PathBuf>,
    source_commit: Option<String>,
    environment_id: Option<String>,
}

#[derive(Clone, Copy, Debug)]
struct ScenarioConfig {
    name: &'static str,
    vectors: usize,
    dimensions: usize,
    k: usize,
    warmups: usize,
    sequential_samples: usize,
    readers: usize,
    concurrent_searches_per_reader: usize,
    writer_operations: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct LatencySummary {
    samples: usize,
    p50_ns: u64,
    p95_ns: u64,
    p99_ns: u64,
    max_ns: u64,
    mean_ns: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct AllocationSummary {
    samples: usize,
    allocations_total: u64,
    allocated_bytes_total: u64,
    allocations_per_search: f64,
    allocated_bytes_per_search: f64,
    scope: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ConcurrencyReport {
    readers: usize,
    searches_per_reader: usize,
    search_latency: LatencySummary,
    idle_writer_lock_wait: LatencySummary,
    idle_writer_end_to_end: LatencySummary,
    concurrent_writer_lock_wait: LatencySummary,
    concurrent_writer_end_to_end: LatencySummary,
    writer_lock_wait_p95_inflation: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ScenarioReport {
    name: String,
    vectors: usize,
    dimensions: usize,
    k: usize,
    warmups: usize,
    sequential_api_latency: LatencySummary,
    isolated_api_allocations: AllocationSummary,
    concurrency: ConcurrencyReport,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
struct RegressionBudgets {
    sequential_p50_percent: f64,
    sequential_p95_percent: f64,
    sequential_p99_percent: f64,
    allocation_bytes_per_search_percent: f64,
    concurrent_search_p95_percent: f64,
    writer_lock_wait_p95_percent: f64,
}

impl Default for RegressionBudgets {
    fn default() -> Self {
        Self {
            sequential_p50_percent: 5.0,
            sequential_p95_percent: 10.0,
            sequential_p99_percent: 15.0,
            allocation_bytes_per_search_percent: 5.0,
            concurrent_search_p95_percent: 10.0,
            writer_lock_wait_p95_percent: 15.0,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct RegressionCheck {
    scenario: String,
    metric: String,
    baseline: f64,
    current: f64,
    allowed_regression_percent: f64,
    change_percent: Option<f64>,
    passed: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ComparisonReport {
    baseline_path: String,
    passed: bool,
    checks: Vec<RegressionCheck>,
    issues: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct RuntimeInfo {
    os: String,
    architecture: String,
    available_parallelism: usize,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
struct MeasurementContract {
    search_path: String,
    writer_path: String,
    allocation_scope: String,
    percentile_method: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct BenchmarkReport {
    schema_version: u32,
    report_schema: String,
    generated_at: String,
    package_version: String,
    source_commit: Option<String>,
    #[serde(default)]
    environment_id: Option<String>,
    profile: String,
    runtime: RuntimeInfo,
    measurement_contract: MeasurementContract,
    regression_budgets: RegressionBudgets,
    scenarios: Vec<ScenarioReport>,
    comparison: Option<ComparisonReport>,
    does_not_establish: Vec<String>,
}

#[tokio::main(flavor = "multi_thread")]
async fn main() -> Result<()> {
    let options = parse_options()?;
    let baseline = if let Some(path) = options.baseline.as_ref() {
        let bytes = fs::read(path)
            .with_context(|| format!("failed to read baseline {}", path.display()))?;
        let report = serde_json::from_slice(&bytes)
            .with_context(|| format!("invalid baseline JSON {}", path.display()))?;
        Some((path.clone(), report))
    } else {
        None
    };
    let configs = profile_configs(&options.profile)?;
    let mut scenarios = Vec::with_capacity(configs.len());

    for config in configs {
        eprintln!(
            "[indexd-bench] scenario={} vectors={} dimensions={}",
            config.name, config.vectors, config.dimensions
        );
        scenarios.push(run_scenario(config).await?);
    }

    let budgets = RegressionBudgets::default();
    let mut report = BenchmarkReport {
        schema_version: 1,
        report_schema: REPORT_SCHEMA.to_string(),
        generated_at: chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
        package_version: env!("CARGO_PKG_VERSION").to_string(),
        source_commit: options.source_commit,
        environment_id: options.environment_id,
        profile: options.profile,
        runtime: RuntimeInfo {
            os: env::consts::OS.to_string(),
            architecture: env::consts::ARCH.to_string(),
            available_parallelism: std::thread::available_parallelism()
                .map(usize::from)
                .unwrap_or(1),
        },
        measurement_contract: MeasurementContract {
            search_path: "in-process Axum /index/search request using the production handler, Tokio RwLock read_owned and spawn_blocking path".to_string(),
            writer_path: "direct VectorStore upsert under the same Tokio RwLock, with lock-wait and end-to-end durations reported separately".to_string(),
            allocation_scope: "process-global counting allocator sampled around isolated in-process API dispatch; concurrent metrics do not claim per-request allocation isolation".to_string(),
            percentile_method: "nearest-rank over sorted nanosecond samples".to_string(),
        },
        regression_budgets: budgets.clone(),
        scenarios,
        comparison: None,
        does_not_establish: vec![
            "production capacity".to_string(),
            "production latency".to_string(),
            "network or reverse-proxy latency".to_string(),
            "ANN activation readiness".to_string(),
            "lock-free search correctness".to_string(),
            "cross-host comparability without a controlled baseline".to_string(),
        ],
    };

    if let Some((baseline_path, baseline_report)) = baseline.as_ref() {
        report.comparison = Some(compare_reports(
            &report,
            baseline_report,
            baseline_path,
            &budgets,
        ));
    }

    let rendered = serde_json::to_string_pretty(&report)? + "\n";
    if let Some(output) = options.output.as_ref() {
        if let Some(parent) = output.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent)
                    .with_context(|| format!("failed to create {}", parent.display()))?;
            }
        }
        fs::write(output, rendered.as_bytes())
            .with_context(|| format!("failed to write {}", output.display()))?;
        eprintln!("[indexd-bench] wrote {}", output.display());
    } else {
        print!("{rendered}");
    }

    if report
        .comparison
        .as_ref()
        .is_some_and(|comparison| !comparison.passed)
    {
        process::exit(2);
    }

    Ok(())
}

async fn run_scenario(config: ScenarioConfig) -> Result<ScenarioReport> {
    let state = Arc::new(AppState::new());
    populate(&state, config).await?;
    let router = api::router(Arc::clone(&state));
    let query = deterministic_vector(0x7ab5_1d39_44e2_9c61, config.dimensions);
    let payload = search_payload(&query, config.k)?;

    for _ in 0..config.warmups {
        let response = dispatch_search(router.clone(), &payload).await;
        validate_search_response(response).await?;
    }

    let mut sequential_latencies = Vec::with_capacity(config.sequential_samples);
    let mut allocation_count = 0u64;
    let mut allocated_bytes = 0u64;
    for _ in 0..config.sequential_samples {
        let request = request_from_payload(&payload)?;
        let service = router.clone();
        let before = AllocationSnapshot::capture();
        let started = Instant::now();
        let response = service
            .oneshot(request)
            .await
            .expect("router is infallible");
        sequential_latencies.push(duration_ns(started.elapsed()));
        let delta = AllocationSnapshot::capture().delta(before);
        allocation_count = allocation_count.saturating_add(delta.count);
        allocated_bytes = allocated_bytes.saturating_add(delta.bytes);
        validate_search_response(response).await?;
    }

    let (idle_waits, idle_end_to_end) =
        measure_writer(&state, config, "idle-writer", false).await?;
    let (concurrent_searches, concurrent_waits, concurrent_end_to_end) =
        measure_concurrent(&state, router, payload, config).await?;

    let idle_wait_summary = summarize(&idle_waits)?;
    let concurrent_wait_summary = summarize(&concurrent_waits)?;
    let writer_lock_wait_p95_inflation = ratio(
        concurrent_wait_summary.p95_ns as f64,
        idle_wait_summary.p95_ns as f64,
    );

    Ok(ScenarioReport {
        name: config.name.to_string(),
        vectors: config.vectors,
        dimensions: config.dimensions,
        k: config.k,
        warmups: config.warmups,
        sequential_api_latency: summarize(&sequential_latencies)?,
        isolated_api_allocations: AllocationSummary {
            samples: config.sequential_samples,
            allocations_total: allocation_count,
            allocated_bytes_total: allocated_bytes,
            allocations_per_search: allocation_count as f64 / config.sequential_samples as f64,
            allocated_bytes_per_search: allocated_bytes as f64
                / config.sequential_samples as f64,
            scope: "process-global allocator delta around isolated Axum dispatch; request construction and response validation excluded".to_string(),
        },
        concurrency: ConcurrencyReport {
            readers: config.readers,
            searches_per_reader: config.concurrent_searches_per_reader,
            search_latency: summarize(&concurrent_searches)?,
            idle_writer_lock_wait: idle_wait_summary,
            idle_writer_end_to_end: summarize(&idle_end_to_end)?,
            concurrent_writer_lock_wait: concurrent_wait_summary,
            concurrent_writer_end_to_end: summarize(&concurrent_end_to_end)?,
            writer_lock_wait_p95_inflation,
        },
    })
}

async fn populate(state: &Arc<AppState>, config: ScenarioConfig) -> Result<()> {
    let mut store = state.store.write().await;
    for index in 0..config.vectors {
        let vector = deterministic_vector(index as u64 + 1, config.dimensions);
        store.upsert(
            NAMESPACE,
            &format!("doc-{index:08}"),
            "chunk-0",
            vector,
            json!({"snippet": format!("benchmark document {index}")}),
        )?;
    }
    Ok(())
}

async fn dispatch_search(router: Router, payload: &Bytes) -> Response<Body> {
    let request = request_from_payload(payload).expect("static benchmark request is valid");
    router.oneshot(request).await.expect("router is infallible")
}

async fn validate_search_response(response: Response<Body>) -> Result<()> {
    if response.status() != StatusCode::OK {
        bail!("search returned HTTP {}", response.status());
    }
    let bytes = axum::body::to_bytes(response.into_body(), RESPONSE_LIMIT_BYTES).await?;
    let payload: Value = serde_json::from_slice(&bytes)?;
    let result_count = payload
        .get("results")
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0);
    if result_count == 0 {
        bail!("search returned no benchmark results");
    }
    Ok(())
}

async fn measure_writer(
    state: &Arc<AppState>,
    config: ScenarioConfig,
    label: &str,
    yield_between: bool,
) -> Result<(Vec<u64>, Vec<u64>)> {
    let mut waits = Vec::with_capacity(config.writer_operations);
    let mut end_to_end = Vec::with_capacity(config.writer_operations);
    for operation in 0..config.writer_operations {
        let vector = deterministic_vector(0x8ca1_0000 + operation as u64, config.dimensions);
        let total_started = Instant::now();
        let lock_started = Instant::now();
        let mut store = state.store.write().await;
        waits.push(duration_ns(lock_started.elapsed()));
        store.upsert(
            NAMESPACE,
            label,
            "chunk-0",
            vector,
            json!({"snippet": label}),
        )?;
        drop(store);
        end_to_end.push(duration_ns(total_started.elapsed()));
        if yield_between {
            tokio::task::yield_now().await;
        }
    }
    Ok((waits, end_to_end))
}

async fn measure_concurrent(
    state: &Arc<AppState>,
    router: Router,
    payload: Bytes,
    config: ScenarioConfig,
) -> Result<(Vec<u64>, Vec<u64>, Vec<u64>)> {
    let barrier = Arc::new(Barrier::new(config.readers + 2));
    let mut reader_handles = Vec::with_capacity(config.readers);

    for _ in 0..config.readers {
        let reader_barrier = Arc::clone(&barrier);
        let reader_router = router.clone();
        let reader_payload = payload.clone();
        let searches = config.concurrent_searches_per_reader;
        reader_handles.push(tokio::spawn(async move {
            reader_barrier.wait().await;
            let mut latencies = Vec::with_capacity(searches);
            for _ in 0..searches {
                let request = request_from_payload(&reader_payload)?;
                let started = Instant::now();
                let response = reader_router
                    .clone()
                    .oneshot(request)
                    .await
                    .expect("router is infallible");
                latencies.push(duration_ns(started.elapsed()));
                if response.status() != StatusCode::OK {
                    bail!("concurrent search returned HTTP {}", response.status());
                }
            }
            Ok::<_, anyhow::Error>(latencies)
        }));
    }

    let writer_barrier = Arc::clone(&barrier);
    let writer_state = Arc::clone(state);
    let writer_handle = tokio::spawn(async move {
        writer_barrier.wait().await;
        tokio::time::sleep(Duration::from_millis(1)).await;
        measure_writer(&writer_state, config, "concurrent-writer", true).await
    });

    barrier.wait().await;

    let mut search_latencies =
        Vec::with_capacity(config.readers * config.concurrent_searches_per_reader);
    for handle in reader_handles {
        search_latencies.extend(handle.await.context("reader task failed")??);
    }
    let (writer_waits, writer_end_to_end) = writer_handle.await.context("writer task failed")??;
    Ok((search_latencies, writer_waits, writer_end_to_end))
}

fn search_payload(query: &[f32], k: usize) -> Result<Bytes> {
    Ok(Bytes::from(serde_json::to_vec(&json!({
        "query": {
            "text": "benchmark query",
            "meta": {"embedding": query},
        },
        "k": k,
        "namespace": NAMESPACE,
        "filters": null,
    }))?))
}

fn request_from_payload(payload: &Bytes) -> Result<Request<Body>> {
    Request::builder()
        .method("POST")
        .uri("/index/search")
        .header("content-type", "application/json")
        .body(Body::from(payload.clone()))
        .context("failed to build benchmark request")
}

fn deterministic_vector(mut state: u64, dimensions: usize) -> Vec<f32> {
    let mut values = Vec::with_capacity(dimensions);
    for _ in 0..dimensions {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        let scaled = ((state >> 40) as f32) / ((1u64 << 24) as f32);
        values.push(scaled - 0.5);
    }
    values
}

fn summarize(samples: &[u64]) -> Result<LatencySummary> {
    if samples.is_empty() {
        bail!("cannot summarize an empty sample set");
    }
    let mut sorted = samples.to_vec();
    sorted.sort_unstable();
    let total = sorted.iter().map(|value| *value as u128).sum::<u128>();
    Ok(LatencySummary {
        samples: sorted.len(),
        p50_ns: nearest_rank(&sorted, 50),
        p95_ns: nearest_rank(&sorted, 95),
        p99_ns: nearest_rank(&sorted, 99),
        max_ns: *sorted.last().expect("non-empty samples"),
        mean_ns: total as f64 / sorted.len() as f64,
    })
}

fn nearest_rank(sorted: &[u64], percentile: usize) -> u64 {
    let rank = (sorted.len() * percentile).div_ceil(100);
    sorted[rank.saturating_sub(1).min(sorted.len() - 1)]
}

fn duration_ns(duration: Duration) -> u64 {
    duration.as_nanos().min(u64::MAX as u128) as u64
}

fn ratio(numerator: f64, denominator: f64) -> Option<f64> {
    if denominator < MIN_RATIO_BASELINE_NS {
        None
    } else {
        Some(numerator / denominator)
    }
}

fn compare_reports(
    current: &BenchmarkReport,
    baseline: &BenchmarkReport,
    baseline_path: &std::path::Path,
    budgets: &RegressionBudgets,
) -> ComparisonReport {
    let mut issues = Vec::new();
    let mut checks = Vec::new();

    if baseline.schema_version != 1 {
        issues.push(format!(
            "baseline schema_version must be 1, got {}",
            baseline.schema_version
        ));
    }
    if baseline.report_schema != REPORT_SCHEMA {
        issues.push(format!(
            "baseline report_schema must be {REPORT_SCHEMA}, got {}",
            baseline.report_schema
        ));
    }
    if baseline.profile != current.profile {
        issues.push(format!(
            "baseline profile {} does not match current profile {}",
            baseline.profile, current.profile
        ));
    }
    match (&baseline.environment_id, &current.environment_id) {
        (Some(baseline_id), Some(current_id)) if baseline_id == current_id => {}
        (Some(baseline_id), Some(current_id)) => issues.push(format!(
            "baseline environment_id {baseline_id:?} does not match current environment_id {current_id:?}"
        )),
        _ => issues.push(
            "baseline comparison requires the same explicit --environment-id in both reports"
                .to_string(),
        ),
    }
    if baseline.package_version != current.package_version {
        issues.push(format!(
            "baseline package_version {} does not match current package_version {}",
            baseline.package_version, current.package_version
        ));
    }
    if baseline.runtime.os != current.runtime.os
        || baseline.runtime.architecture != current.runtime.architecture
        || baseline.runtime.available_parallelism != current.runtime.available_parallelism
    {
        issues.push(format!(
            "baseline runtime {:?} does not match current runtime {:?}",
            baseline.runtime, current.runtime
        ));
    }

    if baseline.measurement_contract != current.measurement_contract {
        issues.push("baseline measurement contract does not match current report".to_string());
    }
    if baseline.regression_budgets != current.regression_budgets {
        issues.push("baseline regression budgets do not match current report".to_string());
    }

    let mut baseline_scenarios = BTreeMap::new();
    for scenario in &baseline.scenarios {
        if baseline_scenarios
            .insert(scenario.name.as_str(), scenario)
            .is_some()
        {
            issues.push(format!(
                "baseline contains duplicate scenario {}",
                scenario.name
            ));
        }
    }
    if baseline_scenarios.len() != current.scenarios.len() {
        issues.push(format!(
            "baseline scenario count {} does not match current scenario count {}",
            baseline_scenarios.len(),
            current.scenarios.len()
        ));
    }
    for scenario in &current.scenarios {
        let Some(previous) = baseline_scenarios.get(scenario.name.as_str()) else {
            issues.push(format!("baseline is missing scenario {}", scenario.name));
            continue;
        };
        if previous.vectors != scenario.vectors
            || previous.dimensions != scenario.dimensions
            || previous.k != scenario.k
            || previous.warmups != scenario.warmups
            || previous.sequential_api_latency.samples != scenario.sequential_api_latency.samples
            || previous.isolated_api_allocations.samples
                != scenario.isolated_api_allocations.samples
            || previous.concurrency.readers != scenario.concurrency.readers
            || previous.concurrency.searches_per_reader != scenario.concurrency.searches_per_reader
            || previous.concurrency.search_latency.samples
                != scenario.concurrency.search_latency.samples
            || previous.concurrency.idle_writer_lock_wait.samples
                != scenario.concurrency.idle_writer_lock_wait.samples
            || previous.concurrency.idle_writer_end_to_end.samples
                != scenario.concurrency.idle_writer_end_to_end.samples
            || previous.concurrency.concurrent_writer_lock_wait.samples
                != scenario.concurrency.concurrent_writer_lock_wait.samples
            || previous.concurrency.concurrent_writer_end_to_end.samples
                != scenario.concurrency.concurrent_writer_end_to_end.samples
        {
            issues.push(format!(
                "scenario {} contract differs between baseline and current report",
                scenario.name
            ));
            continue;
        }
        checks.push(regression_check(
            &scenario.name,
            "sequential_api_latency.p50_ns",
            previous.sequential_api_latency.p50_ns as f64,
            scenario.sequential_api_latency.p50_ns as f64,
            budgets.sequential_p50_percent,
        ));
        checks.push(regression_check(
            &scenario.name,
            "sequential_api_latency.p95_ns",
            previous.sequential_api_latency.p95_ns as f64,
            scenario.sequential_api_latency.p95_ns as f64,
            budgets.sequential_p95_percent,
        ));
        checks.push(regression_check(
            &scenario.name,
            "sequential_api_latency.p99_ns",
            previous.sequential_api_latency.p99_ns as f64,
            scenario.sequential_api_latency.p99_ns as f64,
            budgets.sequential_p99_percent,
        ));
        checks.push(regression_check(
            &scenario.name,
            "isolated_api_allocations.allocated_bytes_per_search",
            previous.isolated_api_allocations.allocated_bytes_per_search,
            scenario.isolated_api_allocations.allocated_bytes_per_search,
            budgets.allocation_bytes_per_search_percent,
        ));
        checks.push(regression_check(
            &scenario.name,
            "concurrency.search_latency.p95_ns",
            previous.concurrency.search_latency.p95_ns as f64,
            scenario.concurrency.search_latency.p95_ns as f64,
            budgets.concurrent_search_p95_percent,
        ));
        checks.push(regression_check(
            &scenario.name,
            "concurrency.concurrent_writer_lock_wait.p95_ns",
            previous.concurrency.concurrent_writer_lock_wait.p95_ns as f64,
            scenario.concurrency.concurrent_writer_lock_wait.p95_ns as f64,
            budgets.writer_lock_wait_p95_percent,
        ));
    }

    let passed = issues.is_empty() && checks.iter().all(|check| check.passed);
    ComparisonReport {
        baseline_path: baseline_path.display().to_string(),
        passed,
        checks,
        issues,
    }
}

fn regression_check(
    scenario: &str,
    metric: &str,
    baseline: f64,
    current: f64,
    allowed_regression_percent: f64,
) -> RegressionCheck {
    let change_percent = if baseline <= f64::EPSILON {
        None
    } else {
        Some(((current - baseline) / baseline) * 100.0)
    };
    let passed = match change_percent {
        Some(change) => change <= allowed_regression_percent,
        None => current <= f64::EPSILON,
    };
    RegressionCheck {
        scenario: scenario.to_string(),
        metric: metric.to_string(),
        baseline,
        current,
        allowed_regression_percent,
        change_percent,
        passed,
    }
}

fn parse_options() -> Result<Options> {
    let mut profile = "smoke".to_string();
    let mut output = None;
    let mut baseline = None;
    let mut source_commit = None;
    let mut environment_id = None;
    let mut arguments = env::args().skip(1);

    while let Some(argument) = arguments.next() {
        match argument.as_str() {
            "--profile" => profile = required_value(&mut arguments, "--profile")?,
            "--output" => output = Some(PathBuf::from(required_value(&mut arguments, "--output")?)),
            "--baseline" => {
                baseline = Some(PathBuf::from(required_value(&mut arguments, "--baseline")?));
            }
            "--source-commit" => {
                source_commit = Some(required_value(&mut arguments, "--source-commit")?);
            }
            "--environment-id" => {
                let value = required_value(&mut arguments, "--environment-id")?;
                if value.trim().is_empty() {
                    bail!("--environment-id must not be empty");
                }
                environment_id = Some(value);
            }
            "--bench" => {}
            "--help" | "-h" => {
                print_help();
                process::exit(0);
            }
            other => bail!("unknown argument {other:?}; use --help"),
        }
    }

    Ok(Options {
        profile,
        output,
        baseline,
        source_commit,
        environment_id,
    })
}

fn required_value(arguments: &mut impl Iterator<Item = String>, flag: &str) -> Result<String> {
    arguments
        .next()
        .with_context(|| format!("{flag} requires a value"))
}

fn print_help() {
    println!(
        "indexd real-workload benchmark\n\n\
         Usage:\n  cargo bench -p indexd --bench indexd_real_workload -- \\\n         --profile smoke|standard|full [--output PATH] [--baseline PATH] \\\n         [--source-commit SHA] [--environment-id STABLE_HOST_ID]\n\n\
         A failed baseline comparison exits with status 2 after writing the report."
    );
}

fn profile_configs(profile: &str) -> Result<Vec<ScenarioConfig>> {
    let configs = match profile {
        "smoke" => vec![
            ScenarioConfig {
                name: "smoke-1k-384",
                vectors: 1_000,
                dimensions: 384,
                k: 10,
                warmups: 3,
                sequential_samples: 12,
                readers: 2,
                concurrent_searches_per_reader: 8,
                writer_operations: 20,
            },
            ScenarioConfig {
                name: "smoke-2500-768",
                vectors: 2_500,
                dimensions: 768,
                k: 10,
                warmups: 3,
                sequential_samples: 12,
                readers: 2,
                concurrent_searches_per_reader: 8,
                writer_operations: 20,
            },
        ],
        "standard" => vec![
            ScenarioConfig {
                name: "standard-5k-384",
                vectors: 5_000,
                dimensions: 384,
                k: 10,
                warmups: 5,
                sequential_samples: 30,
                readers: 4,
                concurrent_searches_per_reader: 15,
                writer_operations: 20,
            },
            ScenarioConfig {
                name: "standard-10k-768",
                vectors: 10_000,
                dimensions: 768,
                k: 10,
                warmups: 5,
                sequential_samples: 30,
                readers: 4,
                concurrent_searches_per_reader: 15,
                writer_operations: 20,
            },
            ScenarioConfig {
                name: "standard-10k-1536",
                vectors: 10_000,
                dimensions: 1_536,
                k: 10,
                warmups: 5,
                sequential_samples: 20,
                readers: 4,
                concurrent_searches_per_reader: 10,
                writer_operations: 20,
            },
        ],
        "full" => vec![
            ScenarioConfig {
                name: "full-10k-384",
                vectors: 10_000,
                dimensions: 384,
                k: 20,
                warmups: 10,
                sequential_samples: 60,
                readers: 8,
                concurrent_searches_per_reader: 25,
                writer_operations: 20,
            },
            ScenarioConfig {
                name: "full-25k-768",
                vectors: 25_000,
                dimensions: 768,
                k: 20,
                warmups: 10,
                sequential_samples: 50,
                readers: 8,
                concurrent_searches_per_reader: 20,
                writer_operations: 20,
            },
            ScenarioConfig {
                name: "full-25k-1536",
                vectors: 25_000,
                dimensions: 1_536,
                k: 20,
                warmups: 8,
                sequential_samples: 40,
                readers: 8,
                concurrent_searches_per_reader: 15,
                writer_operations: 20,
            },
        ],
        other => bail!("unknown profile {other:?}; expected smoke, standard or full"),
    };
    Ok(configs)
}
