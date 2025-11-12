from odoo import models, fields, api

class StockForecastWizard(models.TransientModel):
    _name = 'stock.forecast.wizard'
    _description = 'Asistente de Población de Previsión de Stock'

    def action_populate_forecast_products(self):
        
        forecast_model = self.env['stock.forecast']
        
        
        existing_products_query = forecast_model.search_read([], ['product_id'])
        existing_product_ids = {p['product_id'][0] for p in existing_products_query}
        
        
        all_products = self.env['product.product'].search([
            ('type', '=', 'product')
        ])
        
        
        new_product_ids = set(all_products.ids) - existing_product_ids
        
    
        products_to_create = []
        for product_id in new_product_ids:
            products_to_create.append({
                'product_id': product_id,
                'months_history': 3, # Valor por defecto
            })
            
        if products_to_create:
            forecast_model.create(products_to_create)
            
        
        return {
            'name': 'Previsión de Stock',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.forecast',
            'view_mode': 'tree',
            'view_id': self.env.ref('muemue_stock_forecast.view_stock_forecast_tree').id,
            'target': 'current',
        }