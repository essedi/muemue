from odoo import models, fields, api
from datetime import datetime, timedelta
from collections import defaultdict

class StockForecast(models.Model):
    _name = 'stock.forecast'
    _description = 'Previsión de Stock'
    _order = 'coverage_months asc'

    
    product_id = fields.Many2one(
        'product.product', 
        string="Producto", 
        required=True, 
        ondelete='cascade'
    )
    _sql_constraints = [
        ('product_id_uniq', 'unique(product_id)', 'Ya existe una previsión para este producto.')
    ]

    
    default_code = fields.Char(string="Referencia", related='product_id.default_code')
    product_name = fields.Char(string="Descripción", related='product_id.name')

    
    months_history = fields.Integer(
        string="Meses Hist.", 
        default=3, 
        help="Meses de historial de ventas a calcular."
    )
    
    forecast_months = fields.Integer(
        string="Meses Previsión",
        default=3,
        help="Meses de previsión para calcular el stock entrante."
    )

    
    current_stock = fields.Float(
        compute='_compute_current_stock', 
        string="Stock Mano",
        help="Stock actual en ubicaciones internas."
    )
    incoming_stock = fields.Float(
        compute='_compute_incoming_stock', 
        string="Stock Entrante",
        help="Stock de pedidos de compra en camino DENTRO del período de previsión."
    )

    
    total_sold = fields.Float(
        compute='_compute_sales_data', 
        string="Ventas",
        help="Total de unidades vendidas en el período."
    )
    monthly_average = fields.Float(
        compute='_compute_sales_data', 
        string="Media Mes", 
        digits=(12, 2)
    )

    
    total_available_stock = fields.Float(
        compute='_compute_coverage_data',
        string="Stock Total",
        help="Stock Mano + Stock Entrante"
    )
    coverage_months = fields.Float(
        compute='_compute_coverage_data', 
        string="Meses Cobertura (Meses2)", 
        digits=(12, 2)
    )
    need_reorder = fields.Boolean(
        compute='_compute_coverage_data', 
        string="¿Pedir?"
    )

    

    @api.depends('product_id')
    def _compute_current_stock(self):
        """
        Calcula el stock actual (a mano).
        """
        if not self.product_id:
            self.current_stock = 0
            return
        quants = self.env['stock.quant'].search_read([
            ('product_id', 'in', self.product_id.ids),
            ('location_id.usage', '=', 'internal')
        ], ['product_id', 'quantity'])
        current_stock_map = defaultdict(float)
        for quant in quants:
            current_stock_map[quant['product_id'][0]] += quant['quantity']
        for rec in self:
            rec.current_stock = current_stock_map.get(rec.product_id.id, 0)
    
    @api.depends('product_id', 'forecast_months')
    def _compute_incoming_stock(self):
        """
        Calcula el stock entrante basado en los 'forecast_months'.
        """
        for rec in self:
            if not rec.product_id:
                rec.incoming_stock = 0
                continue
            
            if rec.forecast_months <= 0:
                rec.incoming_stock = 0
                continue

            
            start_dt = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            
            end_date = fields.Date.today() + timedelta(days=rec.forecast_months * 30.44)
            
            end_dt = fields.Datetime.to_datetime(end_date).replace(hour=23, minute=59, second=59)
            
            domain = [
                ('product_id', '=', rec.product_id.id),
                ('state', 'in', ['assigned', 'confirmed', 'waiting', 'partially_available']),
                ('picking_type_id.code', '=', 'incoming'),
                
                
                
                
                ('picking_id.scheduled_date', '!=', False), 
                ('picking_id.scheduled_date', '>=', start_dt), 
                ('picking_id.scheduled_date', '<=', end_dt)
            ]
            
            incoming_moves = self.env['stock.move'].search_read(domain, ['product_uom_qty'])
            rec.incoming_stock = sum(move['product_uom_qty'] for move in incoming_moves)

    @api.depends('product_id', 'months_history')
    def _compute_sales_data(self):
        """
        Calcula las ventas y la media mensual.
        """
        if not self.product_id:
            self.total_sold = 0
            self.monthly_average = 0
            return
        for rec in self:
            if rec.months_history <= 0:
                rec.total_sold = 0
                rec.monthly_average = 0
                continue
            end_date = datetime.now()
            start_date = end_date - timedelta(days=rec.months_history * 30.44)
            sale_lines = self.env['sale.order.line'].search([
                ('order_id.date_order', '>=', start_date),
                ('order_id.date_order', '<=', end_date),
                ('order_id.state', 'in', ['sale', 'done']),
                ('product_id', '=', rec.product_id.id)
            ])
            total_sold = sum(line.product_uom_qty for line in sale_lines)
            rec.total_sold = total_sold
            rec.monthly_average = total_sold / rec.months_history if rec.months_history > 0 else 0

    @api.depends('current_stock', 'incoming_stock', 'monthly_average', 'forecast_months')
    def _compute_coverage_data(self):
        """
        Calcula la cobertura y la necesidad de pedido.
        """
        for rec in self:
            rec.total_available_stock = rec.current_stock + rec.incoming_stock
            if rec.monthly_average > 0:
                rec.coverage_months = rec.total_available_stock / rec.monthly_average
            else:
                rec.coverage_months = 999 if rec.total_available_stock > 0 else 0
            rec.need_reorder = rec.coverage_months < rec.forecast_months

    def action_refresh_stock_data(self):
        """
        Acción para forzar el recálculo del stock manualmente.
        """
        self.sudo()._compute_current_stock()
        self.sudo()._compute_incoming_stock()