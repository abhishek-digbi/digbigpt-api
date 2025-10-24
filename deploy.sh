#!/bin/bash

# DigbiGPT Deployment Script
# This script helps deploy DigbiGPT to various cloud platforms

set -e

echo "🚀 DigbiGPT Deployment Script"
echo "=============================="

# Check if we're in the right directory
if [ ! -f "digbigpt_api.py" ]; then
    echo "❌ Error: digbigpt_api.py not found. Please run this script from the DigbiGPT root directory."
    exit 1
fi

# Check if claims.db exists
if [ ! -f "claims.db" ]; then
    echo "❌ Error: claims.db not found. Please ensure the database file is in the current directory."
    exit 1
fi

echo "✅ Found required files"

# Function to deploy to Railway
deploy_railway() {
    echo "🚂 Deploying to Railway.app..."
    
    # Check if Railway CLI is installed
    if ! command -v railway &> /dev/null; then
        echo "❌ Railway CLI not found. Please install it first:"
        echo "   npm install -g @railway/cli"
        echo "   Then run: railway login"
        exit 1
    fi
    
    # Create railway.json if it doesn't exist
    if [ ! -f "railway.json" ]; then
        cat > railway.json << EOF
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "/app/start.sh",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
EOF
        echo "✅ Created railway.json"
    fi
    
    # Deploy
    railway deploy
    echo "✅ Deployment to Railway completed!"
}

# Function to deploy to Render
deploy_render() {
    echo "🎨 Deploying to Render.com..."
    
    # Create render.yaml if it doesn't exist
    if [ ! -f "render.yaml" ]; then
        cat > render.yaml << EOF
services:
  - type: web
    name: digbigpt
    env: docker
    dockerfilePath: ./Dockerfile
    plan: free
    envVars:
      - key: CLAIMS_DB_PATH
        value: /app/claims.db
      - key: CLAIMS_SERVER_URL
        value: http://localhost:8811
      - key: API_KEY
        generateValue: true
EOF
        echo "✅ Created render.yaml"
    fi
    
    echo "📋 Next steps for Render deployment:"
    echo "   1. Go to https://render.com"
    echo "   2. Connect your GitHub repository"
    echo "   3. Create a new Web Service"
    echo "   4. Use the render.yaml configuration"
    echo "   5. Deploy!"
}

# Function to deploy to DigitalOcean
deploy_digitalocean() {
    echo "🌊 Deploying to DigitalOcean App Platform..."
    
    # Create .do/app.yaml if it doesn't exist
    mkdir -p .do
    if [ ! -f ".do/app.yaml" ]; then
        cat > .do/app.yaml << EOF
name: digbigpt
services:
- name: digbigpt-api
  source_dir: /
  github:
    repo: your-username/digbigpt
    branch: main
  run_command: /app/start.sh
  environment_slug: docker
  instance_count: 1
  instance_size_slug: basic-xxs
  routes:
  - path: /
  envs:
  - key: CLAIMS_DB_PATH
    value: /app/claims.db
  - key: CLAIMS_SERVER_URL
    value: http://localhost:8811
  - key: API_KEY
    value: your-secure-api-key-here
EOF
        echo "✅ Created .do/app.yaml"
    fi
    
    echo "📋 Next steps for DigitalOcean deployment:"
    echo "   1. Go to https://cloud.digitalocean.com/apps"
    echo "   2. Create a new app"
    echo "   3. Connect your GitHub repository"
    echo "   4. Use the .do/app.yaml configuration"
    echo "   5. Deploy!"
}

# Function to create deployment package
create_package() {
    echo "📦 Creating deployment package..."
    
    # Create deployment directory
    mkdir -p digbigpt-deployment
    
    # Copy required files
    cp digbigpt_api.py digbigpt-deployment/
    cp poc/server.py digbigpt-deployment/
    cp poc/requirements.txt digbigpt-deployment/requirements_claims.txt
    cp requirements.txt digbigpt-deployment/requirements_api.txt
    cp claims.db digbigpt-deployment/
    cp Dockerfile digbigpt-deployment/
    cp CustomGPT_Config.json digbigpt-deployment/
    cp DEPLOYMENT_GUIDE.md digbigpt-deployment/
    
    # Create startup script
    cat > digbigpt-deployment/start.sh << 'EOF'
#!/bin/bash
# Start claims server in background
cd /app && python3 server.py &

# Wait for claims server to start
sleep 5

# Start DigbiGPT API
cd /app && python3 digbigpt_api.py
EOF
    chmod +x digbigpt-deployment/start.sh
    
    # Create requirements.txt
    cat > digbigpt-deployment/requirements.txt << EOF
# Claims server dependencies
fastapi>=0.104.0
uvicorn>=0.24.0
duckdb>=1.3.0
tabulate>=0.9.0

# DigbiGPT API dependencies
httpx>=0.25.0
pydantic>=2.0.0
python-dotenv>=1.0.0
python-multipart>=0.0.6
EOF
    
    echo "✅ Deployment package created in digbigpt-deployment/"
    echo "📋 You can now upload this directory to your cloud platform"
}

# Main menu
echo ""
echo "Select deployment option:"
echo "1) Deploy to Railway.app"
echo "2) Deploy to Render.com"
echo "3) Deploy to DigitalOcean"
echo "4) Create deployment package"
echo "5) Test locally"
echo ""

read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        deploy_railway
        ;;
    2)
        deploy_render
        ;;
    3)
        deploy_digitalocean
        ;;
    4)
        create_package
        ;;
    5)
        echo "🧪 Testing locally..."
        echo "Starting DigbiGPT services..."
        
        # Start claims server in background
        cd poc && python3 server.py &
        CLAIMS_PID=$!
        
        # Wait for claims server to start
        sleep 5
        
        # Start DigbiGPT API
        cd .. && python3 digbigpt_api.py &
        API_PID=$!
        
        echo "✅ Services started!"
        echo "   Claims Server: http://localhost:8811"
        echo "   DigbiGPT API: http://localhost:8000"
        echo "   API Docs: http://localhost:8000/docs"
        echo ""
        echo "Press Ctrl+C to stop services"
        
        # Wait for user to stop
        trap "kill $CLAIMS_PID $API_PID; exit" INT
        wait
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac

echo ""
echo "🎉 Deployment process completed!"
echo "📋 Next steps:"
echo "   1. Update CustomGPT_Config.json with your deployed URL"
echo "   2. Set up authentication (API key)"
echo "   3. Import configuration into ChatGPT Enterprise"
echo "   4. Test with sample questions"
echo ""
echo "📖 See DEPLOYMENT_GUIDE.md for detailed instructions"
