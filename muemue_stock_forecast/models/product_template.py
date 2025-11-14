from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    
    in_forecast = fields.Boolean(
        string="Seguir en Previsión de Stock",
        compute='_compute_in_forecast',
        inverse='_set_in_forecast',
        help="Si se marca, todas las variantes de este producto se añadirán a la Previsión de Stock."
    )

    def _compute_in_forecast(self):
        """
        Marca la casilla si encuentra una línea de previsión
        para *cualquiera* de las variantes de este producto.
        """
        # Busca todas las variantes de las plantillas actuales
        all_variants = self.product_variant_ids
        
        # un set con todos los IDs de variantes que están en la previsión
        forecasted_variants = set(
            self.env['stock.forecast'].search([
                ('product_id', 'in', all_variants.ids)
            ]).product_id.ids
        )
        
        for template in self:
            template.in_forecast = any(   # define el estado de la casilla segun lo que devuelva any
                variant_id in forecasted_variants 
                for variant_id in template.product_variant_ids.ids
            )

    def _set_in_forecast(self):
        """Se dispara cuando el usuario
        marca o desmarca la casilla en la plantilla.
        """
        forecast_model = self.env['stock.forecast']
        
        for template in self:
            # todas las variantes de este producto
            variants_to_process = template.product_variant_ids

            if template.in_forecast:
               
                
                # crea líneas solo para las variantes que no la tengan ya
                existing_lines = forecast_model.search([
                    ('product_id', 'in', variants_to_process.ids)
                ])
                existing_variant_ids = set(existing_lines.product_id.ids)

                lines_to_create_vals = []
                for variant in variants_to_process:
                    if variant.id not in existing_variant_ids:
                        lines_to_create_vals.append({
                            'product_id': variant.id,
                        })
                
                if lines_to_create_vals:
                    forecast_model.create(lines_to_create_vals)
            
            else:
                
                
                lines_to_delete = forecast_model.search([
                    ('product_id', 'in', variants_to_process.ids)
                ])
                
                if lines_to_delete:
                    lines_to_delete.unlink() #esto es la funcion que borra las lineas