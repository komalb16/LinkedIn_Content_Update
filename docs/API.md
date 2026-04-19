# 🔌 API Reference

REST API and integration guide for LinkedIn Content Generator.

---

## Base URL

```
http://localhost:8000
```

(Phase 2 feature - docs provided for integration planning)

---

## Authentication

Bearer token authentication:

```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
  http://localhost:8000/posts
```

---

## Endpoints

### Posts

#### Generate Post

```
POST /api/v1/posts/generate
```

**Request:**
```json
{
  "topic": "AI & Machine Learning",
  "post_type": "topic",
  "dry_run": true
}
```

**Response (200 OK):**
```json
{
  "post_id": "post_20240115_001",
  "text": "📌 Building RAG Systems That Actually Work\n\nI spent 6 months getting RAG wrong...",
  "diagram_url": "/diagrams/post_20240115_001.png",
  "preview_image": "data:image/png;base64,...",
  "metadata": {
    "topic": "AI & Machine Learning",
    "post_type": "topic",
    "engagement_score": 0.85,
    "hashtag_count": 5,
    "emoji_count": 4,
    "has_cta": true,
    "has_vulnerability": true
  },
  "draft": true,
  "created_at": "2024-01-15T09:00:00Z"
}
```

---

#### Publish Post

```
POST /api/v1/posts/{post_id}/publish
```

**Request:**
```json
{
  "publish_at": "2024-01-15T09:00:00Z",
  "notify_followers": true
}
```

**Response (200 OK):**
```json
{
  "post_id": "post_20240115_001",
  "status": "published",
  "linkedin_url": "https://www.linkedin.com/...",
  "published_at": "2024-01-15T09:00:00Z"
}
```

---

#### Get Posts

```
GET /api/v1/posts[?limit=10&offset=0&status=published]
```

**Query Parameters:**
- `limit` (int): Max results, default 10
- `offset` (int): Pagination offset, default 0
- `status` (string): published, draft, scheduled
- `topic` (string): Filter by topic
- `post_type` (string): Filter by type

**Response (200 OK):**
```json
{
  "posts": [
    {
      "post_id": "post_20240115_001",
      "text": "...",
      "status": "published",
      "engagement": {
        "comments": 187,
        "likes": 523,
        "reposts": 42
      },
      "created_at": "2024-01-15T09:00:00Z"
    }
  ],
  "total": 127,
  "limit": 10,
  "offset": 0
}
```

---

#### Get Post by ID

```
GET /api/v1/posts/{post_id}
```

**Response (200 OK):**
```json
{
  "post_id": "post_20240115_001",
  "text": "...",
  "diagram": "...",
  "metadata": {},
  "engagement": {
    "comments": 187,
    "likes": 523,
    "reposts": 42
  }
}
```

---

### Analytics

#### Get Engagement Stats

```
GET /api/v1/analytics/engagement[?days=30&post_type=topic]
```

**Query Parameters:**
- `days` (int): Look-back period, default 30
- `post_type` (string): Filter by post type

**Response (200 OK):**
```json
{
  "period": "2024-01-15 to 2024-02-14",
  "by_post_type": {
    "topic": {
      "total_posts": 8,
      "avg_engagement": 245,
      "avg_comments": 187,
      "avg_likes": 523,
      "best_post": "post_20240120_003"
    },
    "interview": {
      "total_posts": 4,
      "avg_engagement": 312
    }
  },
  "top_posts": [
    {
      "post_id": "post_20240120_003",
      "engagement": 523,
      "topic": "System Design"
    }
  ]
}
```

---

#### Get Topic Performance

```
GET /api/v1/analytics/topics[?days=30]
```

**Response (200 OK):**
```json
{
  "topics": [
    {
      "name": "AI & Machine Learning",
      "posts": 8,
      "avg_engagement": 245,
      "top_posts": 3,
      "trending": true
    }
  ]
}
```

---

### Topics

#### List Topics

```
GET /api/v1/topics
```

**Response (200 OK):**
```json
{
  "topics": [
    {
      "name": "AI & Machine Learning",
      "category": "emerging_tech",
      "post_count": 8,
      "last_used": "2024-01-15T09:00:00Z",
      "enabled": true
    }
  ]
}
```

---

#### Add Topic

```
POST /api/v1/topics
```

**Request:**
```json
{
  "name": "Rust Programming",
  "category": "languages",
  "keywords": ["rust", "systems", "performance"],
  "enabled": true
}
```

**Response (201 Created):**
```json
{
  "topic_id": "topic_rust_001",
  "name": "Rust Programming",
  "created_at": "2024-01-15T09:00:00Z"
}
```

---

### Settings

#### Get Settings

```
GET /api/v1/settings
```

**Response (200 OK):**
```json
{
  "auto_post": true,
  "enable_topic_diversity": true,
  "enable_engagement_tracking": true,
  "enable_diagram_rotation": true,
  "schedule_cron": "0 9,21 * * *"
}
```

---

#### Update Settings

```
PUT /api/v1/settings
```

**Request:**
```json
{
  "auto_post": true,
  "enable_topic_diversity": true,
  "schedule_cron": "0 9,21 * * *"
}
```

**Response (200 OK):**
```json
{
  "updated": true,
  "settings": {}
}
```

---

## Error Responses

### 400 Bad Request

```json
{
  "error": "invalid_request",
  "message": "Topic is required",
  "details": {
    "field": "topic",
    "reason": "missing_required_field"
  }
}
```

### 401 Unauthorized

```json
{
  "error": "unauthorized",
  "message": "Invalid or expired API token"
}
```

### 404 Not Found

```json
{
  "error": "not_found",
  "message": "Post not found",
  "resource": "post_20240115_001"
}
```

### 429 Too Many Requests

```json
{
  "error": "rate_limited",
  "message": "API rate limit exceeded",
  "retry_after": 60
}
```

### 500 Server Error

```json
{
  "error": "server_error",
  "message": "Internal server error",
  "request_id": "req_abc123"
}
```

---

## Rate Limiting

- **Free tier**: 100 requests/hour
- **Pro tier**: 1000 requests/hour
- **Enterprise**: Unlimited

Headers included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1705344000
```

---

## Webhooks

Register webhooks for events (Phase 2):

```
POST /api/v1/webhooks
```

**Supported events:**
- `post.created`
- `post.published`
- `post.engagement_updated`
- `engagement.threshold_hit` (>200 comments, etc.)

---

## Code Examples

### Python

```python
import requests

API_URL = "http://localhost:8000/api/v1"
API_TOKEN = "your_token_here"

headers = {"Authorization": f"Bearer {API_TOKEN}"}

# Generate post
response = requests.post(
    f"{API_URL}/posts/generate",
    json={
        "topic": "AI & Machine Learning",
        "post_type": "topic",
        "dry_run": False
    },
    headers=headers
)

post = response.json()
print(f"Post ID: {post['post_id']}")
```

### JavaScript

```javascript
const API_URL = "http://localhost:8000/api/v1";
const API_TOKEN = "your_token_here";

async function generatePost() {
  const response = await fetch(`${API_URL}/posts/generate`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_TOKEN}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      topic: "AI & Machine Learning",
      post_type: "topic",
      dry_run: false
    })
  });

  const post = await response.json();
  console.log(`Post ID: ${post.post_id}`);
}
```

### cURL

```bash
curl -X POST http://localhost:8000/api/v1/posts/generate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "AI & Machine Learning",
    "post_type": "topic",
    "dry_run": false
  }'
```

---

## Integration Examples

### Zapier / Make

```
1. Trigger: On schedule (daily)
2. Action: HTTP POST to /api/v1/posts/generate
3. Data: {"topic": "AI & Machine Learning"}
4. Result: Post published
```

### IFTTT

```
If: New element in spreadsheet
Then: Call /api/v1/posts/generate with topic
```

---

## Backward Compatibility

- API version in URL: `/api/v1/`
- Breaking changes will increment version
- Deprecation notice given 6 months before removal

---

## Support

- **API issues?** See [Troubleshooting](TROUBLESHOOTING.md)
- **Feature request?** [Open issue](https://github.com/yourusername/linkedin-content-generator/issues)
- **Need help?** Email support@example.com
