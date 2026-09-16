# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ============================================================
    # CANALES COMERCIALES
    #
    # Un mismo producto maestro puede estar disponible en uno
    # o varios canales sin necesidad de duplicarlo como:
    #
    # - ONLINE
    # - OFERTA
    # - MAYORISTA
    #
    # Estas banderas indican dónde puede utilizarse el producto.
    # ============================================================

    available_physical_store = fields.Boolean(
        string="Tienda física",
        default=True,
        help="Permite utilizar este producto en tiendas físicas.",
    )

    available_wholesale = fields.Boolean(
        string="Mayorista",
        default=False,
        help="Permite utilizar este producto en operaciones mayoristas.",
    )

    available_online = fields.Boolean(
        string="Tienda digital",
        default=False,
        help=(
            "Permite utilizar este producto en el canal digital. "
            "El canal digital podrá trabajar con sus variantes de talla y color."
        ),
    )

    # ============================================================
    # CONTROL OPERATIVO DE VARIANTES
    #
    # Las variantes reales siguen siendo administradas por Odoo
    # mediante product.attribute y product.template.attribute.line.
    #
    # Este campo únicamente indica si el producto requiere que
    # talla/color sean considerados en operaciones que necesiten
    # detalle de variantes, por ejemplo:
    #
    # - Tienda Digital
    # - Transferencia MODELO -> VARIANTE
    #
    # No crea variantes nuevas ni duplica atributos.
    # ============================================================

    use_operational_variants = fields.Boolean(
        string="Usar variantes operativas",
        default=False,
        help=(
            "Actívelo cuando este producto deba manejar sus variantes "
            "de talla, color u otros atributos en operaciones que "
            "requieran detalle por variante."
        ),
    )
