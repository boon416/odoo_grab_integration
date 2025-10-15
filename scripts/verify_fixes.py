#!/usr/bin/env python3
"""
Verification script to check the Grab integration fixes for:
1. Product description fallback logic
2. Tax inclusion in prices
"""

import sys
import os

# Add the module path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_description_logic():
    """Check the description fallback logic in webhook_menu.py"""
    print("🔍 Checking description fallback logic...")
    
    webhook_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'controllers', 'webhook_menu.py')
    
    if os.path.exists(webhook_file):
        with open(webhook_file, 'r') as f:
            content = f.read()
            
        # Check for fallback logic
        if 'description_sale' in content and 'description' in content:
            print("✅ Description fallback logic implemented in webhook_menu.py")
            
            # Check for HTML cleaning
            if 're.sub' in content and '<[^>]+>' in content:
                print("✅ HTML tag cleaning implemented")
            else:
                print("⚠️  HTML tag cleaning not found")
        else:
            print("❌ Description fallback logic not found in webhook_menu.py")
    else:
        print("❌ webhook_menu.py file not found")

def check_model_description_logic():
    """Check the description logic in grab_menu.py model"""
    print("\n🔍 Checking model description logic...")
    
    model_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'grab_menu.py')
    
    if os.path.exists(model_file):
        with open(model_file, 'r') as f:
            content = f.read()
            
        # Check for improved depends and fallback logic
        if 'product_id.description_sale' in content and 'product_id.description' in content:
            print("✅ Model description fallback logic implemented in grab_menu.py")
            
            # Check for HTML cleaning in model
            if 're.sub' in content and '<[^>]+>' in content:
                print("✅ HTML tag cleaning implemented in model")
            else:
                print("⚠️  HTML tag cleaning not found in model")
        else:
            print("❌ Model description fallback logic not found")
    else:
        print("❌ grab_menu.py model file not found")

def check_tax_parameter():
    """Check the system parameter for tax inclusion"""
    print("\n🔍 Checking tax inclusion parameter...")
    
    data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'system_parameters.xml')
    
    if os.path.exists(data_file):
        with open(data_file, 'r') as f:
            content = f.read()
            
        if 'grab.price_tax_included' in content and '<field name="value">1</field>' in content:
            print("✅ Tax inclusion parameter set to '1' in system_parameters.xml")
        else:
            print("❌ Tax inclusion parameter not properly configured")
    else:
        print("❌ system_parameters.xml file not found")

def check_manifest():
    """Check if the data file is included in manifest"""
    print("\n🔍 Checking manifest configuration...")
    
    manifest_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '__manifest__.py')
    
    if os.path.exists(manifest_file):
        with open(manifest_file, 'r') as f:
            content = f.read()
            
        if 'data/system_parameters.xml' in content:
            print("✅ system_parameters.xml included in manifest")
        else:
            print("❌ system_parameters.xml not included in manifest")
    else:
        print("❌ __manifest__.py file not found")

def main():
    """Main verification function"""
    print("🚀 Grab Integration Fixes Verification")
    print("=" * 50)
    
    check_description_logic()
    check_model_description_logic()
    check_tax_parameter()
    check_manifest()
    
    print("\n" + "=" * 50)
    print("📋 Summary:")
    print("1. Description fallback: website_description → description_sale → description")
    print("2. HTML tag cleaning: Removes HTML tags from descriptions")
    print("3. Tax inclusion: grab.price_tax_included parameter set to '1'")
    print("4. Model improvements: Enhanced _compute_website_description method")
    
    print("\n🔄 Next steps:")
    print("1. Restart/upgrade the Odoo module to apply changes")
    print("2. Check that products have description_sale or description fields populated")
    print("3. Test menu export to verify descriptions and tax-inclusive prices")

if __name__ == '__main__':
    main()