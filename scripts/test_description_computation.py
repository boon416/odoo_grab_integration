#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to check product description computation in Grab menu items
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_description_computation():
    """Test the description computation for Jasmine Green Tea product"""
    
    print("=== Testing Product Description Computation ===")
    
    # This would be the manual test - we'll provide instructions instead
    print("""
    To test the description computation manually:
    
    1. Go to Odoo interface
    2. Navigate to Products > Products
    3. Find 'Jasmine Green Tea' product
    4. Check these fields:
       - Description (General tab)
       - Sales Description (Sales tab)
       - Website Description (if available)
    
    5. Add content to any of these fields, for example:
       Sales Description: "Refreshing jasmine-scented green tea with delicate floral aroma"
    
    6. Save the product
    
    7. Go to Grab Integration > Grab Menus > Menu Items
    8. Find the Jasmine Green Tea item
    9. Check if Website Description field now shows the content
    
    If the field is still empty after adding description to the product:
    - Try refreshing the page
    - Try editing and saving the grab menu item
    - Check the server logs for any errors
    """)

if __name__ == "__main__":
    test_description_computation()