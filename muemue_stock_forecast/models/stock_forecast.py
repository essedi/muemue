from odoo import models, fields, api, _ 
from datetime import datetime, timedelta
from collections import defaultdict
from odoo.exceptions import UserError 
import logging
_logger = logging.getLogger(__name__)

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
        
    )
    reorder_warning= fields.Boolean(
        compute='_compute_coverage_data'
    )


    
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

            warning_limit = rec.forecast_months + (rec.forecast_months / 2.0)
            rec.reorder_warning = (rec.coverage_months > rec.forecast_months) and (rec.coverage_months <= warning_limit)


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
    
    
    
    def _get_incoming_stock_domain(self):
        """
        Función auxiliar que CONSTRUYE el dominio (filtro) para el stock entrante.
        Es usada tanto por _compute_incoming_stock como por action_view_incoming_stock_moves
        para asegurar que la lógica es idéntica.
        """
        
        self.ensure_one()
        
        if self.forecast_months <= 0 or not self.product_id:
            
            return [('id', '=', 0)]

        # 1. Fecha de inicio: HOY a las 00:00:00
        start_dt = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # 2. Fecha de fin: La fecha de hoy + X meses
        end_date = fields.Date.today() + timedelta(days=self.forecast_months * 30.44)
        # 3. Convertir a datetime de FIN del día (23:59:59)
        end_dt = fields.Datetime.to_datetime(end_date).replace(hour=23, minute=59, second=59)
        
        domain = [
            ('product_id', '=', self.product_id.id),
            ('state', 'in', ['assigned', 'confirmed', 'waiting', 'partially_available']),
            ('picking_type_id.code', '=', 'incoming'),
            
            
            ('picking_id.scheduled_date', '!=', False), 
            ('picking_id.scheduled_date', '>=', start_dt), 
            ('picking_id.scheduled_date', '<=', end_dt)
        ]
        return domain


    
    @api.depends('product_id', 'forecast_months')
    def _compute_incoming_stock(self):
        """
        Calcula el stock entrante basado en los 'forecast_months'.
        """
        for rec in self:
            
            domain = rec._get_incoming_stock_domain()
            
            if domain == [('id', '=', 0)]:
                rec.incoming_stock = 0
                continue
                
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

            _logger.debug("start_date %s end_date %s",start_date, end_date)
            sale_lines = self.env['sale.order.line'].search([
                ('order_id.date_order', '>=', start_date),
                ('order_id.date_order', '<=', end_date),
                ('order_id.state', 'in', ['sale', 'done']),
                ('product_id', '=', rec.product_id.id)
            ])
            total_sold = sum(line.product_uom_qty for line in sale_lines)
            rec.total_sold = total_sold
            rec.monthly_average = total_sold / rec.months_history if rec.months_history > 0 else 0

    
    # funcion del boton de la derecha de Stock Entrante
    def action_view_incoming_stock_moves(self):
       
        self.ensure_one() 
        
        domain = self._get_incoming_stock_domain()
        
        
        return {
            'name': 'Movimientos Entrantes Previstos',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move', 
            'view_mode': 'tree,form', 
            'target': 'new', 
            'domain': domain, 
            'context': {
                'search_default_group_by_picking': 1, # Agrupa por Albarán/Recepción
                'search_default_group_by_product': 1,
            }
        }
    def action_open_poblar_wizard(self):
        """
        Esta función es llamada por el nuevo botón "Actualizar Lista de Previsión".
        No importa qué filas estén seleccionadas, solo abre el wizard.
        """
        # Devuelve la acción que abre el wizard de "Poblar"
        return {
            'name': _('Poblar Previsión de Stock'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.forecast.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': False, # No abre un registro, solo el wizard
        }


    def action_refresh_stock_data(self):
        """
        Acción para forzar el recálculo del stock manualmente.
        """
        self.sudo()._compute_current_stock()
        self.sudo()._compute_incoming_stock()
        

    
    def action_launch_order_wizard(self):
        """
        Esta es la función que llama la Acción de Servidor "Pedir".
        Recoge los productos seleccionados y abre el wizard (pop-up).
        """
        
        # 'self' aquí es el conjunto de filas seleccionadas por el usuario
        if not self:
            return

        wizard_line_model = self.env['stock.order.wizard.line']
        wizard_lines = []

        for rec in self:
       

            # Calcular la cantidad a pedir:
            # (Stock Objetivo) - (Esto es la media de ventas * los meses que se quieren cubrir)
            target_stock = rec.monthly_average * rec.forecast_months
            current_and_incoming = rec.total_available_stock
            quantity_to_order = target_stock - current_and_incoming

            # Si el cálculo es negativo (tenemos de más), no pedimos
            if quantity_to_order <= 0:
                quantity_to_order=0
                
            # Buscar el primer proveedor (defecto) de la lista
            default_supplier = rec.product_id.seller_ids[:1].partner_id

            line_vals = {
                'forecast_id': rec.id,
                'product_id': rec.product_id.id,
                'quantity_to_order': quantity_to_order,
                'supplier_id': default_supplier.id if default_supplier else False,
            }
            wizard_lines.append((0, 0, line_vals)) # (0, 0, vals) es el formato para crear One2many

        if not wizard_lines:
            
            raise UserError(_("Ninguno de los productos seleccionados necesita reposición (o ya está pedido)."))


        wizard = self.env['stock.order.wizard'].create({
            'line_ids': wizard_lines
        })

        # Esto devuelve una acción para abrir el pop-up
        return {
            'name': _('Asistente para Pedir Stock'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.order.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new', # 'new' = abrir en pop-up
        }