from odoo import fields, models
from odoo.exceptions import ValidationError


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    # ============================================================
    # MODO DE CONTROL DE PRODUCTOS
    #
    # MODELO:
    # El almacén trabaja comercialmente con el producto agrupado
    # por modelo. Ejemplo: Huánuco, Gamarra y Monarca.
    #
    # VARIANTE:
    # El almacén trabaja exclusivamente con talla/color de forma
    # explícita.
    #
    # MIXTO:
    # El mismo almacén puede trabajar:
    # - Venta unitaria: por variante.
    # - Venta mayorista: por modelo.
    #
    # Ambos modos utilizan el mismo stock físico de Odoo.
    # ============================================================
    product_control_mode = fields.Selection(
        [
            ("model", "Por modelo"),
            ("variant", "Por variantes"),
            ("mixed", "Mixto: modelo y variantes"),
        ],
        string="Control de productos",
        required=True,
        default="model",
        help=(
            "Define cómo trabaja comercialmente este almacén. "
            "Por modelo agrupa el stock de todas las variantes. "
            "Por variantes trabaja con talla y color de forma individual. "
            "Mixto permite trabajar por variantes en venta unitaria "
            "y por modelo en operaciones mayoristas."
        ),
    )

    def _get_effective_product_control_mode(self, operation_mode=None):
        """
        Determina cómo debe trabajar una operación comercial
        dentro del almacén.

        - Almacén por modelo: siempre trabaja por modelo.
        - Almacén por variantes: siempre trabaja por variantes.
        - Almacén mixto: la operación debe indicar explícitamente
        si trabajará por modelo o por variante.
        """
        self.ensure_one()

        # Los almacenes con un único modo no necesitan
        # que la operación indique nada adicional.
        if self.product_control_mode in ("model", "variant"):
            return self.product_control_mode

        # En modo mixto no debemos asumir el comportamiento.
        if operation_mode not in ("model", "variant"):
            raise ValidationError(
                "El almacén '%s' trabaja en modo mixto.\n\n"
                "La operación debe indicar si trabajará "
                "por modelo o por variante." % self.display_name
            )

        return operation_mode

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

    def _get_available_stock_by_variant(self, product_variant):
        """
        Obtiene el stock disponible de una variante específica
        dentro de este almacén.

        No modifica el stock físico de Odoo.
        Este método se utilizará en almacenes que necesiten
        trabajar con talla/color de forma individual.
        """
        self.ensure_one()

        if not product_variant or not self.lot_stock_id:
            return 0.0

        Quant = self.env["stock.quant"]

        return Quant._get_available_quantity(
            product_variant,
            self.lot_stock_id,
        )

    def _get_available_stock_for_operation(
        self,
        product,
        operation_mode=None,
    ):
        """
        Obtiene el stock disponible según la forma de trabajo
        efectiva del almacén y de la operación.

        - Modelo:
        suma el stock de todas las variantes.

        - Variante:
        consulta únicamente la variante indicada.

        En almacenes mixtos, operation_mode es obligatorio.
        """
        self.ensure_one()

        mode = self._get_effective_product_control_mode(operation_mode)

        # ============================================================
        # OPERACIÓN POR MODELO
        # ============================================================
        if mode == "model":

            if product._name == "product.product":
                product_tmpl = product.product_tmpl_id
            elif product._name == "product.template":
                product_tmpl = product
            else:
                raise ValidationError(
                    "Para consultar stock por modelo debe indicar "
                    "un producto o una plantilla de producto."
                )

            return self._get_available_stock_by_template(product_tmpl)

        # ============================================================
        # OPERACIÓN POR VARIANTE
        # ============================================================
        if product._name != "product.product":
            raise ValidationError(
                "Para una operación por variante debe indicar "
                "una variante específica del producto."
            )

        return self._get_available_stock_by_variant(product)

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
