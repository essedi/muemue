from odoo import models, api

class SaleOrder(models.Model):
    _inherit='sale.order'

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
    
        for order in self:
            product_ids = order.order_line.mapped('product_id').ids
            
            if product_ids:
                forecasts = self.env['stock.forecast'].search([
                    ('product_id', 'in', product_ids)
                ])
                
               
                if forecasts:
                    forecasts.action_refresh_stock_data()
                    
        return res
