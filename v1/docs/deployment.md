# DigbiGPT Deployment Guide

## Overview
This guide covers deploying DigbiGPT to various cloud platforms for production use.

## Prerequisites
- Docker installed locally
- Cloud platform account (Railway, Render, AWS, etc.)
- OpenAI API key
- Claims database file (`data/claims.db`)

## Local Development

### Quick Start
```bash
# Clone repository
git clone <repository-url>
cd DigbiGPT

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your OpenAI API key

# Run locally
python src/app.py
```

### Docker Development
```bash
# Build and run with Docker Compose
docker-compose up --build

# Services will be available at:
# - DigbiGPT API: http://localhost:9000
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379
```

## Cloud Deployment Options

### Option 1: Railway.app (Recommended)

**Pros:** Easy deployment, automatic HTTPS, good for production

**Steps:**
1. Install Railway CLI:
   ```bash
   npm install -g @railway/cli
   railway login
   ```

2. Deploy:
   ```bash
   ./scripts/deploy.sh
   # Choose option 1 (Railway)
   ```

3. Set environment variables in Railway dashboard:
   - `OPENAI_API_KEY`
   - `CLAIMS_DB_PATH=/app/data/claims.db`

### Option 2: Render.com

**Pros:** Free tier available, good for testing

**Steps:**
1. Create account at [render.com](https://render.com)
2. Connect your GitHub repository
3. Create a new Web Service
4. Use the generated `render.yaml` configuration
5. Deploy!

### Option 3: AWS Lambda (Serverless)

**Pros:** Serverless, pay-per-use, highly scalable

**Steps:**
1. Package application for Lambda
2. Deploy with API Gateway
3. Configure custom domain
4. Set up authentication

### Option 4: DigitalOcean App Platform

**Pros:** Simple container deployment, good pricing

**Steps:**
1. Create account at [digitalocean.com](https://digitalocean.com)
2. Create app from GitHub repository
3. Configure environment variables
4. Deploy with automatic HTTPS

## Production Configuration

### Environment Variables
```bash
# Required
OPENAI_API_KEY=your-openai-api-key

# Database (for agent configs and logging)
DB_HOST=your-postgres-host
DB_PORT=5432
DB_NAME=digbi_db
DB_USER=digbi_user
DB_PASSWORD=secure-password

# Redis (for caching)
REDIS_HOST=your-redis-host
REDIS_PORT=6379

# LangFuse (for prompt management)
LANGFUSE_PUBLIC_KEY=your-key
LANGFUSE_SECRET_KEY=your-secret
LANGFUSE_HOST=https://cloud.langfuse.com

# Application
ENV=production
DEBUG=False
PORT=9000
```

### Security Considerations
- Use HTTPS for all communications
- Set up API key authentication
- Implement rate limiting
- Monitor for suspicious activity
- Regular security updates

### Performance Optimization
- Enable Redis caching
- Use connection pooling
- Monitor response times
- Set up health checks
- Configure auto-scaling

## ChatGPT Enterprise Integration

### Step 1: Deploy DigbiGPT
Deploy to your chosen cloud platform and get the public URL.

### Step 2: Update Configuration
Edit `deployment/CustomGPT_Config.json`:
```json
{
  "actions": [
    {
      "url": "https://your-deployed-url.com/api/digbigpt/ask",
      "authentication": {
        "type": "bearer",
        "token": "{{$env.API_KEY}}"
      }
    }
  ]
}
```

### Step 3: Import to ChatGPT Enterprise
1. Go to ChatGPT Enterprise settings
2. Import the Custom GPT configuration
3. Test with sample questions

### Step 4: Test Integration
Try these example queries:
- "Which customers spent the most on rosuvastatin in 2024?"
- "Show me the hypertension cohort summary for 2023"
- "How many members started GI medications in Q1 2024?"

## Monitoring and Maintenance

### Health Checks
Monitor these endpoints:
- `GET /api/health` - Service health
- `GET /api/digbigpt/agents` - Agent availability
- `GET /api/digbigpt/tools` - Tool availability

### Logging
- All queries are logged with timestamps
- User activity is tracked
- Error logs are maintained
- Performance metrics are collected

### Updates
- Regular security updates
- Database schema updates
- New tool additions
- Performance optimizations

## Troubleshooting

### Common Issues

**Service won't start:**
- Check environment variables
- Verify database connectivity
- Check port availability

**API calls failing:**
- Verify OpenAI API key
- Check network connectivity
- Review error logs

**Database errors:**
- Ensure claims.db exists
- Check file permissions
- Verify DuckDB installation

### Debug Mode
Enable debug mode for development:
```bash
export DEBUG=True
export ENV=development
python src/app.py
```

## Backup and Recovery

### Database Backup
```bash
# Backup claims database
cp data/claims.db backups/claims-$(date +%Y%m%d).db
```

### Configuration Backup
```bash
# Backup configuration
cp src/config/agents.yaml backups/agents-$(date +%Y%m%d).yaml
```

### Recovery Process
1. Restore database file
2. Restore configuration
3. Restart services
4. Verify functionality

## Scaling Considerations

### Horizontal Scaling
- Use load balancer
- Multiple service instances
- Shared database and cache

### Vertical Scaling
- Increase memory allocation
- Optimize database queries
- Enable caching

### Cost Optimization
- Use appropriate instance sizes
- Implement caching
- Monitor resource usage
- Optimize database queries

## Support

For deployment issues:
1. Check the logs for errors
2. Verify environment variables
3. Test each component individually
4. Review this documentation
5. Contact the development team


