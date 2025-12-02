from odoo import models,api

class PurchaseOrder(models.Model):
    _inherit='purchase.order'

    def button_confirm(self):
        res=super(PurchaseOrder,self).button_confirm()

        for order in self:
            product_ids=order.order_line.mapped('product_id').ids

            if product_ids:
                forecasts=self.env['stock.forecast'].search([('product_id','in',product_ids)])

                if forecasts:
                    forecasts.action_refresh_stock_data()
        
        return res