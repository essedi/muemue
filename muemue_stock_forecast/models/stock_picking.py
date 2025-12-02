from odoo import models,api

class StockPicking(models.Model):
    _inherit='stock.picking'

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        
        for picking in self:
           
            if picking.picking_type_code == 'incoming':
                
                product_ids = picking.move_ids.mapped('product_id').ids
                
                if product_ids:
                    
                    forecasts = self.env['stock.forecast'].search([
                        ('product_id', 'in', product_ids)
                    ])
                    
                    if forecasts:
                        forecasts.action_refresh_stock_data()
                        
        return res   