#!/bin/bash

# DigbiGPT Deployment Script
# This script helps deploy DigbiGPT to various cloud platforms

set -e

echo "🚀 DigbiGPT Deployment Script"
echo "=============================="

# Check if we're in the right directory
if [ ! -f "src/app.py" ]; then
    echo "❌ Error: src/app.py not found. Please run this script from the DigbiGPT root directory."
    exit 1
fi

# Check if claims.db exists
if [ ! -f "data/claims.db" ]; then
    echo "❌ Error: data/claims.db not found. Please ensure the database file is in the data/ directory."
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
        value: /app/data/claims.db
      - key: OPENAI_API_KEY
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

# Function to create deployment package
create_package() {
    echo "📦 Creating deployment package..."
    
    # Create deployment directory
    mkdir -p digbigpt-deployment
    
    # Copy required files
    cp -r src/ digbigpt-deployment/
    cp -r data/ digbigpt-deployment/
    cp requirements.txt digbigpt-deployment/
    cp Dockerfile digbigpt-deployment/
    cp deployment/CustomGPT_Config.json digbigpt-deployment/
    
    # Create startup script
    cat > digbigpt-deployment/start.sh << 'EOF'
#!/bin/bash
# Start DigbiGPT API
cd /app && python src/app.py
EOF
    chmod +x digbigpt-deployment/start.sh
    
    echo "✅ Deployment package created in digbigpt-deployment/"
    echo "📋 You can now upload this directory to your cloud platform"
}

# Main menu
echo ""
echo "Select deployment option:"
echo "1) Deploy to Railway.app"
echo "2) Deploy to Render.com"
echo "3) Create deployment package"
echo "4) Test locally"
echo ""

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        deploy_railway
        ;;
    2)
        deploy_render
        ;;
    3)
        create_package
        ;;
    4)
        echo "🧪 Testing locally..."
        echo "Starting DigbiGPT service..."
        
        # Start DigbiGPT API
        python src/app.py &
        API_PID=$!
        
        echo "✅ Service started!"
        echo "   DigbiGPT API: http://localhost:9000"
        echo "   API Docs: http://localhost:9000/docs"
        echo ""
        echo "Press Ctrl+C to stop service"
        
        # Wait for user to stop
        trap "kill $API_PID; exit" INT
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
echo "   1. Update deployment/CustomGPT_Config.json with your deployed URL"
echo "   2. Set up authentication (API key)"
echo "   3. Import configuration into ChatGPT Enterprise"
echo "   4. Test with sample questions"
echo ""
echo "📖 See docs/deployment.md for detailed instructions"


