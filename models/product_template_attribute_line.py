from odoo import api, models


class ProductTemplateAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    def _get_templates_with_model_stock_enabled(self):
        templates = self.mapped("product_tmpl_id")

        return templates.filtered(
            lambda template: bool(
                template.with_context(active_test=False).product_variant_ids.filtered(
                    lambda variant: (variant.active and variant.is_unclassified_variant)
                )
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        # Evita ejecutar nuevamente la sincronización
        # cuando el propio módulo está ajustando atributos técnicos.
        if self.env.context.get("skip_model_stock_sync"):
            return super().create(vals_list)

        template_ids = {
            vals.get("product_tmpl_id")
            for vals in vals_list
            if vals.get("product_tmpl_id")
        }

        templates = (
            self.env["product.template"]
            .browse(list(template_ids))
            .filtered(
                lambda template: bool(
                    template.with_context(
                        active_test=False
                    ).product_variant_ids.filtered(
                        lambda variant: (
                            variant.active and variant.is_unclassified_variant
                        )
                    )
                )
            )
        )

        lines = super().create(vals_list)

        for template in templates.exists():
            template.with_context(
                skip_model_stock_sync=True
            )._ensure_unclassified_variant()

        return lines

    def write(self, vals):
        # Solo resincronizamos cuando cambian
        # los valores de la línea o su estado.
        should_sync = not self.env.context.get("skip_model_stock_sync") and (
            "value_ids" in vals or "active" in vals
        )

        templates = (
            self._get_templates_with_model_stock_enabled()
            if should_sync
            else self.env["product.template"]
        )

        result = super().write(vals)

        for template in templates.exists():
            template.with_context(
                skip_model_stock_sync=True
            )._ensure_unclassified_variant()

        return result
