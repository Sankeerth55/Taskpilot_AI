#!/bin/bash
set -e  # Exit immediately if any command fails

echo "🚀 Taskpilot AI - Render Deployment Script"
echo "=========================================="

# Step 1: Verify Vite project at repo root
echo ""
echo "✓ Step 1: Verifying Vite project structure..."
if [ ! -f "vite.config.ts" ]; then
    echo "❌ Error: vite.config.ts not found. Are you in the project root?"
    exit 1
fi
if [ ! -f "package.json" ]; then
    echo "❌ Error: package.json not found."
    exit 1
fi
echo "✅ Vite project confirmed at repository root"

# Step 2: Run production build
echo ""
echo "✓ Step 2: Running production build..."
npm run build
echo "✅ Build completed successfully"

# Step 3: Verify dist/index.html exists
echo ""
echo "✓ Step 3: Verifying build output..."
if [ ! -f "dist/index.html" ]; then
    echo "❌ Error: dist/index.html not found. Build may have failed."
    exit 1
fi
echo "✅ Build output verified (dist/index.html exists)"

# Step 4: Check if vite.config.ts changed
echo ""
echo "✓ Step 4: Checking for changes..."
if git diff --quiet vite.config.ts && git diff --cached --quiet vite.config.ts; then
    echo "ℹ️  No changes detected in vite.config.ts"
else
    echo "✅ Changes detected in vite.config.ts - staging file"
    git add vite.config.ts
    git commit -m "Fix: Update vite.config.ts for Render Static Site deployment"
    echo "✅ Committed vite.config.ts changes"
fi

# Step 5: Push to main
echo ""
echo "✓ Step 5: Pushing to GitHub..."
git push origin main
echo "✅ Pushed to origin/main"

# Step 6: Success message
echo ""
echo "=========================================="
echo "✅ SUCCESS! Deployment preparation complete"
echo "=========================================="
echo ""
echo "📋 Next Steps:"
echo "   1. Go to your Render Dashboard"
echo "   2. Navigate to your Static Site"
echo "   3. Click 'Manual Deploy' → 'Deploy latest commit'"
echo ""
echo "🔧 Render Settings (verify these):"
echo "   Build Command:     npm run build"
echo "   Publish Directory: dist"
echo ""
echo "🌐 Your site will be live at:"
echo "   https://taskpilot-ai-frontend.onrender.com"
echo ""
