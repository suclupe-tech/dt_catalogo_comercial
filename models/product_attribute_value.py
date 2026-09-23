# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    # ============================================================
    # VALOR TÉCNICO PARA STOCK SIN CLASIFICAR
    #
    # Permite identificar valores especiales como:
    #
    # COLOR: SIN CLASIFICAR
    # TALLA: SIN CLASIFICAR
    #
    # Estos valores servirán únicamente para construir la variante
    # técnica que almacena el stock trabajado por modelo.
    # ============================================================

    is_unclassified_value = fields.Boolean(
        string="Valor sin clasificar",
        default=False,
        copy=False,
        index=True,
        help=(
            "Indica que este valor de atributo es técnico y se utiliza "
            "para representar stock todavía no clasificado."
        ),
    )
