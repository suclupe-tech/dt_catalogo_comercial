# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockCommercialAllocation(models.Model):
    _name = "dt.stock.commercial.allocation"
    _description = "Asignación Comercial de Stock"

    # Permite registrar en el chatter quién realizó
    # modificaciones sobre la oferta.
    _inherit = ["mail.thread", "mail.activity.mixin"]

    _order = "id desc"

    _rec_name = "name"

    # ============================================================
    # NOMBRE DESCRIPTIVO DEL REGISTRO
    # ============================================================

    name = fields.Char(
        string="Referencia",
        compute="_compute_name",
        store=True,
    )

    @api.depends("warehouse_id", "product_tmpl_id")
    def _compute_name(self):
        """
        Genera un nombre descriptivo para identificar
        fácilmente cada asignación comercial.
        """
        for record in self:
            if record.product_tmpl_id and record.warehouse_id:
                record.name = "%s - %s" % (
                    record.product_tmpl_id.display_name,
                    record.warehouse_id.display_name,
                )
            elif record.product_tmpl_id:
                record.name = record.product_tmpl_id.display_name
            elif record.warehouse_id:
                record.name = record.warehouse_id.display_name
            else:
                record.name = "Nueva asignación"

    # ============================================================
    # ASIGNACIÓN COMERCIAL DE STOCK
    #
    # Odoo continúa siendo la fuente principal del stock físico.
    #
    # Este modelo registra únicamente qué cantidad del stock
    # existente se encuentra destinada a OFERTA.
    #
    # Stock normal disponible:
    #
    # Stock físico real - Stock asignado a oferta
    # ============================================================

    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Almacén",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )

    commercial_condition = fields.Selection(
        [
            ("offer", "Oferta"),
        ],
        string="Condición comercial",
        required=True,
        default="offer",
        index=True,
    )

    quantity = fields.Float(
        string="Cantidad en oferta",
        required=True,
        default=0.0,
        tracking=True,
    )

    # ============================================================
    # PRECIO DE OFERTA
    # ============================================================

    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        related="warehouse_id.company_id.currency_id",
        readonly=True,
    )

    offer_price = fields.Monetary(
        string="Precio de oferta",
        currency_field="currency_id",
        default=0.0,
        tracking=True,
    )

    # ============================================================
    # VIGENCIA OPCIONAL DE LA OFERTA
    # ============================================================

    use_validity = fields.Boolean(
        string="Usar vigencia",
        default=False,
        tracking=True,
        help=(
            "Si está activado, la oferta solo estará disponible "
            "entre la fecha de inicio y la fecha de fin."
        ),
    )

    validity_date_from = fields.Date(
        string="Fecha de inicio",
        tracking=True,
    )

    validity_date_to = fields.Date(
        string="Fecha de fin",
        tracking=True,
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        tracking=True,
    )

    note = fields.Char(
        string="Observación",
    )

    # ============================================================
    # RESUMEN DE STOCK COMERCIAL
    #
    # Estos campos son informativos.
    # No modifican el stock físico de Odoo.
    # ============================================================

    physical_stock = fields.Float(
        string="Stock total disponible",
        compute="_compute_stock_summary",
        readonly=True,
    )

    normal_commercial_stock = fields.Float(
        string="Stock para venta regular",
        compute="_compute_stock_summary",
        readonly=True,
    )

    @api.depends(
        "warehouse_id",
        "product_tmpl_id",
        "quantity",
        "active",
        "use_validity",
        "validity_date_from",
        "validity_date_to",
    )
    def _compute_stock_summary(self):
        """
        Muestra el stock físico disponible y el stock que queda
        disponible para venta regular.

        La cantidad asignada a oferta solo se descuenta cuando
        la oferta está activa y, si usa vigencia, cuando la fecha
        actual se encuentra dentro del rango configurado.
        """

        for record in self:

            record.physical_stock = 0.0
            record.normal_commercial_stock = 0.0

            if not record.warehouse_id or not record.product_tmpl_id:
                continue

            # ====================================================
            # STOCK FÍSICO REAL
            # ====================================================
            physical_stock = record.warehouse_id._get_available_stock_by_template(
                record.product_tmpl_id
            )

            # ====================================================
            # DETERMINAR SI LA OFERTA RESERVA STOCK ACTUALMENTE
            # ====================================================
            offer_stock = 0.0

            if record.active:

                # Sin vigencia:
                # la cantidad permanece reservada hasta agotarse.
                if not record.use_validity:
                    offer_stock = record.quantity

                # Con vigencia:
                # solo reserva durante el periodo configurado.
                else:
                    today = fields.Date.context_today(record)

                    if (
                        record.validity_date_from
                        and record.validity_date_to
                        and record.validity_date_from <= today
                        and today <= record.validity_date_to
                    ):
                        offer_stock = record.quantity

            # ====================================================
            # RESUMEN
            # ====================================================
            record.physical_stock = physical_stock

            # Nunca mostrar stock comercial negativo.
            record.normal_commercial_stock = max(
                physical_stock - offer_stock,
                0.0,
            )

    # ============================================================
    # VALIDACIÓN DE STOCK DISPONIBLE
    #
    # Todavía trabajamos por producto maestro.
    # Sumamos el stock real de todas sus variantes dentro de la
    # ubicación principal del almacén.
    #
    # Más adelante, cuando conectemos almacenes por variantes,
    # podremos endurecer esta validación a product.product.
    # ============================================================

    @api.constrains(
        "warehouse_id",
        "product_tmpl_id",
        "quantity",
        "active",
    )
    def _check_offer_quantity_against_stock(self):

        Quant = self.env["stock.quant"]

        for record in self:

            if not record.active:
                continue

            if not record.warehouse_id or not record.product_tmpl_id:
                continue

            stock_location = record.warehouse_id.lot_stock_id

            if not stock_location:
                raise ValidationError(
                    "El almacén seleccionado no tiene una ubicación principal de stock."
                )

            physical_stock = 0.0

            for product in record.product_tmpl_id.product_variant_ids:

                physical_stock += Quant._get_available_quantity(
                    product,
                    stock_location,
                )

            if record.quantity > physical_stock:

                raise ValidationError(
                    "No puede asignar %.2f unidades a oferta.\n\n"
                    "Stock físico disponible en %s: %.2f"
                    % (
                        record.quantity,
                        record.warehouse_id.display_name,
                        physical_stock,
                    )
                )

    # ============================================================
    # VALIDAR VIGENCIA DE LA OFERTA
    # ============================================================

    @api.constrains(
        "use_validity",
        "validity_date_from",
        "validity_date_to",
    )
    def _check_offer_validity_dates(self):
        for record in self:

            # Si no se usa vigencia, las fechas no son obligatorias.
            if not record.use_validity:
                continue

            # Si se activa la vigencia, deben indicarse ambas fechas.
            if not record.validity_date_from or not record.validity_date_to:
                raise ValidationError(
                    "Debe indicar la fecha de inicio y la fecha de fin " "de la oferta."
                )

            # La fecha final nunca puede ser anterior a la inicial.
            if record.validity_date_to < record.validity_date_from:
                raise ValidationError(
                    "La fecha de fin de la oferta no puede ser anterior "
                    "a la fecha de inicio."
                )

    # ============================================================
    # RESTRICCIONES SQL
    # ============================================================

    _quantity_non_negative = models.Constraint(
        "CHECK(quantity >= 0)",
        "La cantidad asignada a oferta no puede ser negativa.",
    )

    _unique_offer_allocation = models.Constraint(
        "UNIQUE(warehouse_id, product_tmpl_id, commercial_condition)",
        "Ya existe una asignación de oferta para este producto en este almacén.",
    )
