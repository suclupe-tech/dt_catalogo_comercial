# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockCommercialAllocation(models.Model):
    _name = "dt.stock.commercial.allocation"
    _description = "Asignación Comercial de Stock"
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
    )

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto",
        required=True,
        index=True,
        ondelete="restrict",
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
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
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
    )
    def _compute_stock_summary(self):
        """
        Muestra el stock disponible real de Odoo y el stock
        que queda disponible para venta normal después de
        separar la cantidad destinada a oferta.
        """

        for record in self:

            record.physical_stock = 0.0
            record.normal_commercial_stock = 0.0

            if not record.warehouse_id or not record.product_tmpl_id:
                continue

            # Stock disponible real de Odoo
            physical_stock = record.warehouse_id._get_available_stock_by_template(
                record.product_tmpl_id
            )

            # Mientras editamos el registro usamos directamente
            # su cantidad asignada para que el cálculo se actualice
            # inmediatamente en pantalla.
            offer_stock = record.quantity if record.active else 0.0

            record.physical_stock = physical_stock

            # Nunca mostramos stock comercial negativo
            record.normal_commercial_stock = max(
                physical_stock - offer_stock,
                0.0,
            )

    # ============================================================
    # RESTRICCIONES SQL
    # ============================================================

    # Impide registrar cantidades negativas
    _quantity_non_negative = models.Constraint(
        "CHECK(quantity >= 0)",
        "La cantidad asignada a oferta no puede ser negativa.",
    )

    # Impide duplicar la misma asignación de oferta
    # para un producto dentro del mismo almacén
    _unique_offer_allocation = models.Constraint(
        "UNIQUE(warehouse_id, product_tmpl_id, commercial_condition)",
        "Ya existe una asignación de oferta para este producto en este almacén.",
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
