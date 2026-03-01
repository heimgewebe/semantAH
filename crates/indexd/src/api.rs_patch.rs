use serde::{Deserialize, Serialize, Deserializer, de::Error};
use serde_json::{Value, Map};

#[derive(Debug, Serialize, Default, Clone)]
pub struct TypedMetadata {
    pub embedding: Option<Vec<f32>>,
    #[serde(flatten)]
    pub extra: Map<String, Value>,
}

impl<'de> Deserialize<'de> for TypedMetadata {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let mut map: Map<String, Value> = Map::deserialize(deserializer)?;

        // If 'embedding' is present, parse it and leave it in `extra` if it's null,
        // or just rely on a custom representation.
        // Actually, if we just parse the map, we can manually build the TypedMetadata.
        let embedding = match map.remove("embedding") {
            Some(Value::Array(arr)) => {
                let mut vec = Vec::with_capacity(arr.len());
                for val in arr {
                    if let Some(f) = val.as_f64() {
                        vec.push(f as f32);
                    } else {
                        return Err(D::Error::custom("embedding must be an array of numbers"));
                    }
                }
                Some(vec)
            }
            Some(Value::Null) => {
                // If null, we want it to be considered explicitly provided but null.
                // We can put it back into extra so the handler can detect it.
                map.insert("embedding".to_string(), Value::Null);
                None
            }
            Some(_) => return Err(D::Error::custom("embedding must be an array of numbers")),
            None => None,
        };

        Ok(TypedMetadata { embedding, extra: map })
    }
}
