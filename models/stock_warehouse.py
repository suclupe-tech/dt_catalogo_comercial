# -*- coding: utf-8 -*-

from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    # ============================================================
    # MODO DE CONTROL DE PRODUCTOS
    #
    # MODELO:
    # El almacén trabaja comercialmente con el producto agrupado
    # por modelo. Las variantes no forman parte de su operación
    # cotidiana.
    #
    # VARIANTE:
    # El almacén necesita trabajar con talla y color de forma
    # explícita, como ocurre con la Tienda Digital.
    # ============================================================
    product_control_mode = fields.Selection(
        [
            ("model", "Por modelo"),
            ("variant", "Por variantes"),
        ],
        string="Control de productos",
        required=True,
        default="model",
        help=(
            "Define cómo trabaja este almacén con los productos. "
            "Los almacenes físicos normalmente trabajan por modelo, "
            "mientras que un almacén digital puede requerir control "
            "por talla y color."
        ),
    )

    # ============================================================
    # CÁLCULO DE STOCK COMERCIAL
    #
    # El stock físico/disponible de Odoo NO se modifica.
    #
    # Para la operación comercial separamos:
    #
    # Stock normal = Stock disponible Odoo - Stock asignado a oferta
    #
    # Ejemplo:
    # Stock disponible Odoo: 302
    # Stock en oferta:          1
    # Stock normal:           301
    # ============================================================

    def _get_available_stock_by_template(self, product_tmpl):
        """
        Obtiene el stock disponible de un producto maestro
        dentro de este almacén, sumando todas sus variantes.
        """
        self.ensure_one()

        if not product_tmpl or not self.lot_stock_id:
            return 0.0

        Quant = self.env["stock.quant"]

        available_stock = 0.0

        # Sumamos el stock disponible de todas las variantes
        # pertenecientes al producto maestro.
        for product in product_tmpl.product_variant_ids:
            available_stock += Quant._get_available_quantity(
                product,
                self.lot_stock_id,
            )

        return available_stock

    def _get_offer_allocated_quantity(self, product_tmpl):
        self.ensure_one()

        if not product_tmpl:
            return 0.0

        today = fields.Date.context_today(self)

        # ============================================================
        # SOLO CONTABILIZAR OFERTAS VIGENTES
        #
        # Una oferta reserva stock cuando:
        # - Está activa.
        # - No usa vigencia, o
        # - La fecha actual está entre inicio y fin.
        #
        # Las ofertas futuras o vencidas dejan de reservar stock
        # automáticamente para la venta regular.
        # ============================================================
        allocations = self.env["dt.stock.commercial.allocation"].search(
            [
                ("warehouse_id", "=", self.id),
                ("product_tmpl_id", "=", product_tmpl.id),
                ("commercial_condition", "=", "offer"),
                ("active", "=", True),
                "|",
                ("use_validity", "=", False),
                "&",
                ("validity_date_from", "<=", today),
                ("validity_date_to", ">=", today),
            ]
        )

        return sum(allocations.mapped("quantity"))

    def _get_normal_commercial_quantity(self, product_tmpl):
        """
        Calcula el stock que puede utilizar el canal comercial normal.
        """
        self.ensure_one()

        available_stock = self._get_available_stock_by_template(product_tmpl)

        offer_stock = self._get_offer_allocated_quantity(product_tmpl)

        # Nunca mostramos disponibilidad comercial negativa.
        return max(
            available_stock - offer_stock,
            0.0,
        )
