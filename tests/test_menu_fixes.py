# -*- coding: utf-8 -*-
"""
Test script to verify the fixes for product description and tax inclusion
"""

from odoo.tests.common import TransactionCase
from unittest.mock import patch


class TestGrabMenuFixes(TransactionCase):
    
    def setUp(self):
        super().setUp()
        
        # Create a test product with different description fields
        self.product = self.env['product.template'].create({
            'name': 'Test Product',
            'list_price': 10.0,
            'description': 'Main product description',
            'description_sale': 'Sales description for customers',
            'website_description': '',  # Empty to test fallback
        })
        
        # Create a grab menu structure
        self.grab_menu = self.env['grab.menu'].create({
            'name': 'Test Menu',
            'merchant_id': 'TEST_MERCHANT',
        })
        
        self.grab_section = self.env['grab.menu.section'].create({
            'name': 'Test Section',
            'menu_id': self.grab_menu.id,
        })
        
        self.grab_category = self.env['grab.menu.category'].create({
            'name': 'Test Category',
            'section_id': self.grab_section.id,
        })
        
        self.grab_item = self.env['grab.menu.item'].create({
            'product_id': self.product.id,
            'category_id': self.grab_category.id,
        })
    
    def test_description_fallback_to_description_sale(self):
        """Test that description falls back to description_sale when website_description is empty"""
        # Ensure website_description is empty
        self.product.website_description = ''
        self.grab_item._compute_website_description()
        
        # Should fallback to description_sale
        self.assertEqual(self.grab_item.website_description, 'Sales description for customers')
    
    def test_description_fallback_to_main_description(self):
        """Test that description falls back to main description when both website_description and description_sale are empty"""
        # Ensure both website_description and description_sale are empty
        self.product.website_description = ''
        self.product.description_sale = ''
        self.grab_item._compute_website_description()
        
        # Should fallback to main description
        self.assertEqual(self.grab_item.website_description, 'Main product description')
    
    def test_website_description_priority(self):
        """Test that website_description has priority when available"""
        # Set website_description
        self.product.website_description = 'Website specific description'
        self.grab_item._compute_website_description()
        
        # Should use website_description
        self.assertEqual(self.grab_item.website_description, 'Website specific description')
    
    def test_html_tag_cleaning(self):
        """Test that HTML tags are cleaned from descriptions"""
        # Set description with HTML tags
        self.product.description_sale = '<p>Sales description with <strong>HTML</strong> tags</p>'
        self.product.website_description = ''
        self.grab_item._compute_website_description()
        
        # Should clean HTML tags
        self.assertEqual(self.grab_item.website_description, 'Sales description with HTML tags')
    
    @patch('odoo.http.request')
    def test_tax_inclusion_parameter(self, mock_request):
        """Test that the system parameter for tax inclusion is set correctly"""
        # Mock the environment
        mock_request.env = self.env
        
        # Check that the system parameter is set to include tax
        param_value = self.env['ir.config_parameter'].sudo().get_param('grab.price_tax_included', '0')
        
        # After our fix, this should be '1'
        self.assertEqual(param_value, '1', "grab.price_tax_included should be set to '1' to include tax")


if __name__ == '__main__':
    # This is a basic test that can be run manually
    print("Test script created successfully!")
    print("To run these tests, use: python -m pytest tests/test_menu_fixes.py")