#!/usr/bin/env python3
"""
Test script for bulk description refresh functionality.
This script helps verify that the bulk refresh method works correctly.

To use this script in Odoo shell:
1. Start Odoo shell: python3 odoo-bin shell -d your_database_name
2. Copy and paste this code into the shell
"""

def test_bulk_description_refresh():
    """Test the bulk description refresh functionality"""
    
    # Get the grab menu item model
    GrabMenuItem = env['grab.menu.item']
    
    print("=== Testing Bulk Description Refresh ===")
    
    # Get all grab menu items
    all_items = GrabMenuItem.search([])
    print(f"Found {len(all_items)} grab menu items")
    
    if not all_items:
        print("No grab menu items found. Please create some first.")
        return
    
    # Show current state
    print("\n=== Current State ===")
    items_with_descriptions = 0
    items_without_descriptions = 0
    
    for item in all_items:
        has_desc = bool(item.website_description and item.website_description.strip())
        if has_desc:
            items_with_descriptions += 1
            print(f"✓ {item.name}: Has description")
        else:
            items_without_descriptions += 1
            print(f"✗ {item.name}: No description")
            
            # Check if product has any description fields
            if item.product_id:
                p = item.product_id
                website_desc = getattr(p, 'website_description', None)
                sale_desc = getattr(p, 'description_sale', None)
                main_desc = getattr(p, 'description', None)
                
                available_descs = []
                if website_desc and website_desc.strip():
                    available_descs.append("website_description")
                if sale_desc and sale_desc.strip():
                    available_descs.append("description_sale")
                if main_desc and main_desc.strip():
                    available_descs.append("description")
                
                if available_descs:
                    print(f"  → Product has: {', '.join(available_descs)}")
                else:
                    print(f"  → Product has no descriptions")
    
    print(f"\nSummary: {items_with_descriptions} with descriptions, {items_without_descriptions} without")
    
    # Test the bulk refresh method
    print("\n=== Testing Bulk Refresh Method ===")
    
    # Call the bulk refresh method on any item (it processes all items)
    if all_items:
        result = all_items[0].action_bulk_refresh_descriptions()
        print("Bulk refresh completed!")
        print(f"Result: {result}")
    
    # Check state after refresh
    print("\n=== State After Refresh ===")
    items_with_descriptions_after = 0
    items_without_descriptions_after = 0
    
    # Refresh the records to get updated data
    all_items.invalidate_cache()
    
    for item in all_items:
        has_desc = bool(item.website_description and item.website_description.strip())
        if has_desc:
            items_with_descriptions_after += 1
            print(f"✓ {item.name}: Has description")
        else:
            items_without_descriptions_after += 1
            print(f"✗ {item.name}: No description")
    
    print(f"\nAfter refresh: {items_with_descriptions_after} with descriptions, {items_without_descriptions_after} without")
    
    # Show improvement
    improvement = items_with_descriptions_after - items_with_descriptions
    if improvement > 0:
        print(f"🎉 Improved! {improvement} items now have descriptions")
    elif improvement == 0:
        print("No change - items that could get descriptions already had them")
    else:
        print("⚠️  Something went wrong - fewer items have descriptions now")

def test_single_item_refresh():
    """Test refreshing a single item"""
    
    GrabMenuItem = env['grab.menu.item']
    
    print("\n=== Testing Single Item Refresh ===")
    
    # Find an item without description
    items_without_desc = GrabMenuItem.search([('website_description', '=', False)])
    
    if not items_without_desc:
        print("No items without descriptions found")
        return
    
    item = items_without_desc[0]
    print(f"Testing with item: {item.name}")
    
    # Check product descriptions
    if item.product_id:
        p = item.product_id
        print(f"Product: {p.name}")
        
        website_desc = getattr(p, 'website_description', None)
        sale_desc = getattr(p, 'description_sale', None)
        main_desc = getattr(p, 'description', None)
        
        print(f"Website description: {website_desc or 'Empty'}")
        print(f"Sales description: {sale_desc or 'Empty'}")
        print(f"Main description: {main_desc or 'Empty'}")
    
    # Test refresh
    print("Calling action_refresh_description...")
    result = item.action_refresh_description()
    print(f"Result: {result}")
    
    # Check if description was populated
    item.invalidate_cache()
    print(f"Description after refresh: {item.website_description or 'Still empty'}")

# Instructions for manual testing
print("""
To test the bulk description refresh functionality:

1. In Odoo shell, run:
   test_bulk_description_refresh()

2. To test single item refresh:
   test_single_item_refresh()

3. Or test manually in the UI:
   - Go to Grab Integration > Menu Items
   - Click "Refresh All Descriptions" button in the list view
   - Check the notification message for results

4. For individual items:
   - Open any grab menu item form
   - Click "Refresh Description" or "Debug Description" buttons
""")