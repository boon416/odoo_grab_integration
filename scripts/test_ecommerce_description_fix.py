#!/usr/bin/env python3
"""
Test script to verify that ecommerce description fields are being picked up correctly.
This script helps test the fix for the ecommerce description issue.

To use this script in Odoo shell:
1. Start Odoo shell: python3 odoo-bin shell -d your_database_name
2. Copy and paste this code into the shell
"""

def test_ecommerce_description_fix():
    """Test that ecommerce description fields are being picked up"""
    
    print("=== Testing Ecommerce Description Fix ===")
    
    # Get the grab menu item model
    GrabMenuItem = env['grab.menu.item']
    
    # Find the Jasmine Green Tea item
    jasmine_item = GrabMenuItem.search([('name', 'ilike', 'Jasmine Green Tea')], limit=1)
    
    if not jasmine_item:
        print("❌ Jasmine Green Tea grab menu item not found")
        return
    
    print(f"✅ Found grab menu item: {jasmine_item.name}")
    
    # Check the product
    if not jasmine_item.product_id:
        print("❌ No product linked to this grab menu item")
        return
    
    product = jasmine_item.product_id
    print(f"✅ Linked product: {product.name}")
    
    # Check all description fields
    print("\n=== Product Description Fields ===")
    
    description_fields = [
        'website_description',
        'description_ecommerce', 
        'ecommerce_description',
        'description_website',
        'public_description',
        'description_sale',
        'description',
    ]
    
    found_descriptions = {}
    
    for field_name in description_fields:
        if hasattr(product, field_name):
            field_value = getattr(product, field_name, None)
            if field_value and field_value.strip():
                found_descriptions[field_name] = field_value.strip()
                print(f"✅ {field_name}: {field_value[:100]}{'...' if len(field_value) > 100 else ''}")
            else:
                print(f"❌ {field_name}: Empty")
        else:
            print(f"⚠️  {field_name}: Field not available")
    
    # Test the computation
    print("\n=== Testing Computation ===")
    
    # Store old description
    old_description = jasmine_item.website_description or ""
    print(f"Old computed description: {old_description or 'Empty'}")
    
    # Trigger computation
    jasmine_item._compute_website_description()
    
    # Check new description
    new_description = jasmine_item.website_description or ""
    print(f"New computed description: {new_description or 'Empty'}")
    
    # Check if it improved
    if new_description and not old_description:
        print("🎉 SUCCESS! Description is now populated!")
    elif new_description and new_description != old_description:
        print("🎉 SUCCESS! Description was updated!")
    elif new_description:
        print("✅ Description was already populated correctly")
    else:
        print("❌ Description is still empty")
        
        if found_descriptions:
            print("⚠️  Product has description fields but they're not being picked up:")
            for field_name, value in found_descriptions.items():
                print(f"   - {field_name}: {value[:50]}...")
        else:
            print("ℹ️  Product has no description content in any field")

def test_debug_method():
    """Test the enhanced debug method"""
    
    print("\n=== Testing Enhanced Debug Method ===")
    
    GrabMenuItem = env['grab.menu.item']
    jasmine_item = GrabMenuItem.search([('name', 'ilike', 'Jasmine Green Tea')], limit=1)
    
    if jasmine_item:
        print("Calling action_debug_description...")
        result = jasmine_item.action_debug_description()
        print("Debug method result:")
        print(result.get('params', {}).get('message', 'No message'))
    else:
        print("❌ Jasmine Green Tea item not found")

# Instructions for manual testing
print("""
To test the ecommerce description fix:

1. In Odoo shell, run:
   test_ecommerce_description_fix()

2. To test the enhanced debug method:
   test_debug_method()

3. Or test manually in the UI:
   - Go to the Jasmine Green Tea grab menu item
   - Click "Debug Description" to see all available fields
   - Click "Refresh Description" to trigger recomputation
   - Check if the Website Description field is now populated

4. If it's still not working:
   - Check the debug output to see which field contains the ecommerce description
   - The field might have a different name than expected
""")