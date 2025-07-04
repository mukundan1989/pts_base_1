#!/bin/bash

echo "🔧 Building Enhanced WASM Module..."
echo "=================================="

# Check if we're in the right directory
if [ ! -d "adf_test" ]; then
    echo "❌ Error: adf_test directory not found. Please run this from the project root."
    exit 1
fi

# Clean previous build artifacts
echo "🧹 Cleaning previous build artifacts..."
rm -rf adf_test/pkg
rm -rf public/wasm/adf_test*

# Build the WASM module
echo "🏗️  Building WASM module..."
cd adf_test
cargo build --release
if [ $? -ne 0 ]; then
    echo "❌ Cargo build failed!"
    exit 1
fi

# Use wasm-pack to generate JS bindings
wasm-pack build --target web --out-dir ../public/wasm --release
if [ $? -ne 0 ]; then
    echo "❌ wasm-pack build failed!"
    exit 1
fi

echo "✅ Build completed successfully!"

# Verify the enhanced function is exported
cd ..
echo ""
echo "🔍 Verifying Enhanced Functions..."
echo "================================="

if grep -q "calculate_complete_adf_test" public/wasm/adf_test.d.ts; then
    echo "✅ Enhanced function 'calculate_complete_adf_test' found in TypeScript definitions!"
else
    echo "❌ Enhanced function 'calculate_complete_adf_test' NOT found in TypeScript definitions!"
    echo "   This means the WASM build didn't include the enhanced functions."
    echo ""
    echo "🔍 Available functions in WASM module:"
    grep "export function" public/wasm/adf_test.d.ts || echo "No exported functions found"
    exit 1
fi

if grep -q "CompleteAdfResult" public/wasm/adf_test.d.ts; then
    echo "✅ Enhanced result type 'CompleteAdfResult' found in TypeScript definitions!"
else
    echo "❌ Enhanced result type 'CompleteAdfResult' NOT found in TypeScript definitions!"
    exit 1
fi

echo ""
echo "🎉 SUCCESS! Enhanced WASM module built and verified!"
echo "   You can now use the enhanced calculate_complete_adf_test function."
echo ""
echo "📋 Next Steps:"
echo "1. Update your worker to use calculate_complete_adf_test instead of JavaScript calculation"
echo "2. Test the enhanced precision in your ADF test results"