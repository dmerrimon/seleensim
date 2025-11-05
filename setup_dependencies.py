#!/usr/bin/env python3
"""
Dependency Setup Script for Ilana TA-Aware System
Installs and verifies all required dependencies
"""

import os
import sys
import subprocess
import importlib
from pathlib import Path

class DependencyInstaller:
    def __init__(self):
        self.required_packages = {
            # Core ML packages
            'transformers': 'transformers>=4.21.0',
            'torch': 'torch>=1.12.0',
            'sklearn': 'scikit-learn>=1.1.0',
            'numpy': 'numpy>=1.21.0',
            'pandas': 'pandas>=1.4.0',
            
            # Vector databases
            'chromadb': 'chromadb>=0.4.0',
            
            # Web framework
            'fastapi': 'fastapi>=0.100.0',
            'uvicorn': 'uvicorn>=0.23.0',
            'pydantic': 'pydantic>=2.0.0',
            
            # Text processing
            'nltk': 'nltk>=3.8.0',
            
            # Utilities
            'tqdm': 'tqdm>=4.65.0',
            'python_dotenv': 'python-dotenv>=1.0.0'
        }
        
        self.optional_packages = {
            'pinecone': 'pinecone-client>=2.2.0',
            'redis': 'redis>=4.5.0',
            'spacy': 'spacy>=3.6.0'
        }
        
    def check_python_version(self):
        """Check if Python version is compatible"""
        if sys.version_info < (3, 8):
            print("❌ Python 3.8+ required. Current version:", sys.version)
            return False
        print(f"✅ Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        return True
    
    def install_package(self, package_name, package_spec):
        """Install a single package"""
        try:
            print(f"📦 Installing {package_name}...")
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", package_spec
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f"✅ {package_name} installed successfully")
                return True
            else:
                print(f"❌ Failed to install {package_name}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout installing {package_name}")
            return False
        except Exception as e:
            print(f"❌ Error installing {package_name}: {e}")
            return False
    
    def verify_installation(self, package_name):
        """Verify a package is properly installed"""
        try:
            importlib.import_module(package_name)
            print(f"✅ {package_name} verified")
            return True
        except ImportError:
            print(f"❌ {package_name} not found after installation")
            return False
    
    def install_requirements_file(self):
        """Install from requirements file if it exists"""
        req_file = Path(__file__).parent / "requirements_complete.txt"
        if req_file.exists():
            print(f"📋 Installing from {req_file}")
            try:
                result = subprocess.run([
                    sys.executable, "-m", "pip", "install", "-r", str(req_file)
                ], capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    print("✅ Requirements file installed successfully")
                    return True
                else:
                    print(f"⚠️ Some packages failed: {result.stderr}")
                    return False
            except Exception as e:
                print(f"❌ Failed to install requirements: {e}")
                return False
        return False
    
    def setup_nltk_data(self):
        """Download required NLTK data"""
        try:
            import nltk
            print("📚 Downloading NLTK data...")
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            nltk.download('wordnet', quiet=True)
            print("✅ NLTK data downloaded")
            return True
        except Exception as e:
            print(f"⚠️ NLTK data download failed: {e}")
            return False
    
    def test_core_functionality(self):
        """Test that core components work"""
        print("\n🧪 Testing Core Functionality...")
        
        # Test TA Classifier
        try:
            sys.path.append(str(Path(__file__).parent))
            from therapeutic_area_classifier import create_ta_classifier
            classifier = create_ta_classifier()
            result = classifier.detect_therapeutic_area("cancer study")
            print(f"✅ TA Classifier: {result.therapeutic_area}")
        except Exception as e:
            print(f"❌ TA Classifier failed: {e}")
        
        # Test Optimization Engine
        try:
            from optimization_rule_engine import create_optimization_engine
            engine = create_optimization_engine()
            print(f"✅ Optimization Engine: {len(engine.frequency_thresholds)} TAs")
        except Exception as e:
            print(f"❌ Optimization Engine failed: {e}")
        
        # Test Explainability
        try:
            from explainability_api import create_explainability_service
            service = create_explainability_service()
            print(f"✅ Explainability: {len(service.regulatory_sources)} sources")
        except Exception as e:
            print(f"❌ Explainability failed: {e}")
    
    def run_full_setup(self):
        """Run complete dependency setup"""
        print("🚀 Starting Ilana Dependency Setup...\n")
        
        # Check Python version
        if not self.check_python_version():
            return False
        
        # Upgrade pip first
        print("📦 Upgrading pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      capture_output=True)
        
        # Try installing from requirements file first
        if self.install_requirements_file():
            print("✅ Bulk installation completed")
        else:
            # Fallback to individual package installation
            print("📦 Installing packages individually...")
            
            failed_packages = []
            for package_name, package_spec in self.required_packages.items():
                if not self.install_package(package_name, package_spec):
                    failed_packages.append(package_name)
            
            if failed_packages:
                print(f"\n⚠️ Failed to install: {', '.join(failed_packages)}")
                print("These packages are required for full functionality")
        
        # Install optional packages
        print("\n📦 Installing optional packages...")
        for package_name, package_spec in self.optional_packages.items():
            self.install_package(package_name, package_spec)
        
        # Setup additional data
        self.setup_nltk_data()
        
        # Test functionality
        self.test_core_functionality()
        
        print("\n🎯 Dependency setup complete!")
        print("Run 'python test_installation.py' to verify everything works")
        
        return True

if __name__ == "__main__":
    installer = DependencyInstaller()
    installer.run_full_setup()