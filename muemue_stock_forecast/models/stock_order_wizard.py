from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import defaultdict

class StockOrderWizard(models.TransientModel):
    _name = 'stock.order.wizard'
    _description = 'Asistente para Pedir Stock'

    line_ids = fields.One2many(
        'stock.order.wizard.line', 
        'wizard_id', 
        string="Líneas de Producto"
    )

    def action_generate_purchase_orders(self):
        """
        Esta es la lógica del botón "Aceptar".
        Agrupa las líneas por proveedor y crea Pedidos de Compra.
        """
        if not self.line_ids:
            raise UserError("No hay líneas para pedir.")

        # Agrupa líneas por proveedor
        lines_by_supplier = defaultdict(lambda: self.env['stock.order.wizard.line'])
        for line in self.line_ids:
            if not line.supplier_id:
                raise UserError(f"Por favor, selecciona un proveedor para el producto '{line.product_id.name}'.")
            if line.quantity_to_order == 0:
                line.quantity_to_order=0
              
            lines_by_supplier[line.supplier_id] |= line

        po_model = self.env['purchase.order']
        po_line_model = self.env['purchase.order.line']
        created_pos = []

        # Crear un Pedido de Compra (PO) por cada proveedor
        for supplier, lines in lines_by_supplier.items():
            po_vals = {
                'partner_id': supplier.id,
                'state': 'draft',
                'date_order': fields.Datetime.now(),
                #Aqui luego se podrian poner mas valores
            }
            new_po = po_model.create(po_vals)
            created_pos.append(new_po.id)

            # Crear las líneas del Pedido de Compra
            for line in lines:
                product = line.product_id
                supplier = line.supplier_id
                  
                  #seller_ids devuelve una lista de product.supplierinfo, en este tipo de objeto estan las propiedades del supplier

                  #aqui se escoge el product.supplierinfo del proveedor 
                seller_info = product.seller_ids.filtered(
                    lambda s: s.partner_id.id == supplier.id
                )
                unit_price= 0.0
                if seller_info:
                    unit_price=seller_info[0].price
                po_line_vals = {
                    'order_id': new_po.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.quantity_to_order,
                    'price_unit': unit_price,
                    'date_planned': fields.Date.today(),
                    'name': line.product_id.display_name,
                    'product_uom': line.product_id.uom_po_id.id or line.product_id.uom_id.id,
                }
                po_line_model.create(po_line_vals)
        
        # Abrir la lista de Pedidos de Compra recién creados
        if not created_pos:
            raise UserError("No se crearon pedidos (cantidades a 0).")

        return {
            'name': _('Pedidos de Compra Creados'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created_pos)],
        }


class StockOrderWizardLine(models.TransientModel):
    _name = 'stock.order.wizard.line'
    _description = 'Línea de Asistente para Pedir Stock'

    wizard_id = fields.Many2one('stock.order.wizard')
    forecast_id = fields.Many2one('stock.forecast', string="Línea de Previsión")
    product_id = fields.Many2one('product.product', string="Producto", readonly=True)
    
    supplier_info_ids = fields.One2many(
        related='product_id.seller_ids',
        string="Info de Proveedores"
    )
    
    
    supplier_id = fields.Many2one(
        'res.partner', 
        string="Proveedor", 
        required=True
    )
    
    quantity_to_order = fields.Float(string="Cantidad a Pedir", digits='Product Unit of Measure')

    supplier_partner_ids = fields.Many2many(
        'res.partner', 
        compute='_compute_supplier_partner_ids',
        string="Proveedores Válidos"
    )

    @api.depends('product_id')
    def _compute_supplier_partner_ids(self):
        for line in self:
            line.supplier_partner_ids = line.product_id.seller_ids.partner_id