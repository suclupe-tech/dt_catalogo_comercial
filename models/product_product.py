# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    # ============================================================
    # VARIANTE TÉCNICA - STOCK SIN CLASIFICAR
    #
    # Esta bandera identifica la variante utilizada para almacenar
    # el stock que las tiendas físicas manejan únicamente por modelo.
    #
    # Ejemplo:
    #
    # POLO TROPICAL
    # - SIN CLASIFICAR / SIN CLASIFICAR  <- variante técnica
    # - Blanco / S
    # - Blanco / M
    # - Negro / S
    #
    # La variante técnica no representa una talla o color físico.
    # Sirve como contenedor del stock todavía no clasificado.
    # ============================================================

    is_unclassified_variant = fields.Boolean(
        string="Variante sin clasificar",
        default=False,
        copy=False,
        index=True,
        help=(
            "Indica que esta variante es utilizada internamente para "
            "almacenar stock gestionado únicamente por modelo."
        ),
    )
