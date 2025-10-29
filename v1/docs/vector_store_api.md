# Vector Store API

These endpoints allow uploading files with metadata to an existing OpenAI vector store.

## Upload File

`POST /api/vector-stores/{vector_store_id}/files`

Upload a new file and attach it to the specified vector store. The request must use
`multipart/form-data` with the file and optional JSON metadata.

### Form Fields
- `file` – The file to upload
- `attributes` – *(optional)* JSON string of key-value metadata

### Example using `curl`
```bash
curl -X POST \
  -F "file=@document.pdf" \
  -F 'attributes={"category":"docs"}' \
  http://localhost:9000/api/vector-stores/vs_123/files
```

### Response
- **200** File uploaded successfully
- **400** Invalid attributes format
- **500** Error uploading file

## Update File Metadata

`PUT /api/vector-stores/{vector_store_id}/files/{file_id}`

Update the metadata on an existing vector store file.

### JSON Body
```json
{
  "attributes": {"category": "docs"}
}
```

### Response
- **200** File updated
- **400** Invalid attributes
- **500** Error updating file

## Get File (Vector Store)

`GET /api/vector-stores/{vector_store_id}/files/{file_id}`

Retrieve a vector store file by id. Returns the full vector store file object including current attributes.

### Response
- **200** File retrieved
- **500** Error retrieving file

## Get File Attributes

`GET /api/vector-stores/{vector_store_id}/files/{file_id}/attributes`

Retrieve only the attributes (metadata) for a vector store file.

### Response
- **200** Attributes retrieved
- **500** Error retrieving attributes

## Clear File Attributes

`DELETE /api/vector-stores/{vector_store_id}/files/{file_id}/attributes`

Remove all attributes from a vector store file (reset to empty attributes).

Query params
- `force_recreate` – optional boolean. If `true`, detaches and reattaches the file to the vector store if clearing via update does not remove attributes (edge cases or eventual consistency). Defaults to `false`.

### Response
- **200** Attributes cleared
- **500** Error clearing attributes

## Using File Filters

When running an agent with a File Search tool, you can filter which files are considered by attaching attributes to each file and passing `file_filters` with your run.

- Store attributes on a file via upload or update:
  - Upload: `-F 'attributes={"category":"installation","language":"en","platform":"ios"}'`
  - Update: `{ "attributes": { "category": "installation", "language": "en", "platform": "ios" } }`

- Pass filters when running the agent (the service normalizes your input for OpenAI):
  - Single value: `{"category": "installation"}` → equality filter
  - Any-of multiple values: `{"topic": ["cgm", "setup"]}` → OR over boolean flags
    - The server expands list values into flag-style keys on update and filter:
      - Attributes update with lists becomes `{ "topic_cgm": 1, "topic_setup": 1 }`
      - Filters become `{"type":"or","filters":[{"type":"eq","key":"topic_cgm","value":1},{"type":"eq","key":"topic_setup","value":1}]}`
  - Multiple keys: `{"category": "installation", "language": "en"}` → AND across keys

Notes
- Default top-level operator is AND across different keys.
- List values are interpreted as OR across the listed values for that key, using flag keys `<key>_<value>` with value `1`.
- Filters take effect only for agents configured with the relevant `vector_store_ids` that contain the attributed file(s).

### Attribute update behavior for arrays
When you update vector store file attributes and provide an array for a key, the service converts it into individual boolean flags of the form `<key>_<value>: 1` and drops the original list key:

Input:
```json
{
  "attributes": { "topic": ["cgm", "setup"] }
}
```

Stored attributes:
```json
{ "topic_cgm": 1, "topic_setup": 1 }
```
