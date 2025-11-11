from odoo import models, fields, api
from datetime import datetime, timedelta
from collections import defaultdict

class StockForecast(models.Model):
    _name = 'stock.forecast'
    _description = 'Previsión de Stock'

    @api.model
    def get_sold_products(self, months=6):
        """Obtiene productos vendidos en los últimos X meses"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months*30)
        
        # Buscar líneas de venta en el período
        sale_lines = self.env['sale.order.line'].search([
            ('order_id.date_order', '>=', start_date),
            ('order_id.date_order', '<=', end_date),
            ('order_id.state', 'in', ['sale', 'done']),
            ('product_id.type', '=', 'product')  # Solo productos almacenables
        ])
        
        # Agrupar por producto
        product_sales = defaultdict(float)
        for line in sale_lines:
            product_sales[line.product_id] += line.product_uom_qty
            
        return product_sales

    @api.model
    def calculate_stock_forecast(self, months_history=6):
        """Calcula la previsión de stock"""
        products_data = []
        product_sales = self.get_sold_products(months_history)
        
        for product, total_sold in product_sales.items():
            # Calcular media mensual
            monthly_average = total_sold / months_history
            
            # Obtener stock actual
            stock_quant = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id.usage', '=', 'internal')
            ], limit=1)
            
            current_stock = stock_quant.quantity if stock_quant else 0
            
            # Calcular meses de cobertura (evitar división por cero)
            coverage_months = current_stock / monthly_average if monthly_average > 0 else 0
            
            products_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'default_code': product.default_code,
                'total_sold': total_sold,
                'monthly_average': monthly_average,
                'current_stock': current_stock,
                'coverage_months': coverage_months,
                'need_reorder': coverage_months < 2  # Alerta si menos de 2 meses
            })
        
        return sorted(products_data, key=lambda x: x['coverage_months'])

    @api.model
    def get_forecast_data(self, months=6):
        """Método para llamar desde la vista"""
        return self.calculate_stock_forecast(months)