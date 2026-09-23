from odoo import fields, models
from odoo.exceptions import UserError


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

    # ============================================================
    # STOCK SIN CLASIFICAR
    #
    # Crea automáticamente una variante técnica para representar
    # el stock manejado únicamente por modelo.
    #
    # Ejemplo:
    #
    # POLO TROPICAL
    # - Blanco / S
    # - Blanco / M
    # - Negro / S
    # - Negro / M
    # - SIN CLASIFICAR / SIN CLASIFICAR
    #
    # La lógica es dinámica y funciona con cualquier cantidad de
    # atributos que realmente generen variantes.
    # ============================================================

    def _ensure_unclassified_variant(self):
        self.ensure_one()

        AttributeValue = self.env["product.attribute.value"]
        Exclusion = self.env["product.template.attribute.exclusion"]

        # --------------------------------------------------------
        # Obtener únicamente atributos que crean variantes reales.
        # Los atributos configurados como "no_variant" no participan.
        # --------------------------------------------------------
        variant_lines = self.attribute_line_ids.filtered(
            lambda line: line.attribute_id.create_variant != "no_variant"
        )

        if not variant_lines:
            raise UserError(
                "El producto no tiene atributos configurados para crear variantes."
            )

        # Por ahora trabajaremos con variantes creadas normalmente.
        # Esto evita que una variante técnica quede pendiente de creación.
        dynamic_lines = variant_lines.filtered(
            lambda line: line.attribute_id.create_variant == "dynamic"
        )

        if dynamic_lines:
            raise UserError(
                "El producto utiliza atributos con creación dinámica de variantes. "
                "Para utilizar stock SIN CLASIFICAR, los atributos operativos "
                "deben crear variantes automáticamente."
            )

        technical_values = {}

        # --------------------------------------------------------
        # 1. Crear o reutilizar el valor global SIN CLASIFICAR
        #    para cada atributo.
        # --------------------------------------------------------
        for line in variant_lines:
            attribute = line.attribute_id

            technical_value = AttributeValue.search(
                [
                    ("attribute_id", "=", attribute.id),
                    ("is_unclassified_value", "=", True),
                ],
                limit=1,
            )

            if not technical_value:
                technical_value = AttributeValue.create(
                    {
                        "name": "SIN CLASIFICAR",
                        "attribute_id": attribute.id,
                        "is_unclassified_value": True,
                    }
                )

            technical_values[line.id] = technical_value

            # Agregar el valor técnico a este modelo si todavía no existe.
            if technical_value not in line.value_ids:
                line.write(
                    {
                        "value_ids": [(4, technical_value.id)],
                    }
                )

        # --------------------------------------------------------
        # 2. Obtener los PTAV ya creados por Odoo para este modelo.
        # --------------------------------------------------------
        technical_ptavs = self.env["product.template.attribute.value"]

        for line in variant_lines:
            technical_value = technical_values[line.id]

            technical_ptav = line.product_template_value_ids.filtered(
                lambda ptav: (ptav.product_attribute_value_id == technical_value)
            )

            if len(technical_ptav) != 1:
                raise UserError(
                    "No se pudo identificar correctamente el valor "
                    "SIN CLASIFICAR del atributo "
                    f"{line.attribute_id.display_name}."
                )

            technical_ptavs |= technical_ptav

        # --------------------------------------------------------
        # 3. Crear exclusiones.
        #
        # Cada SIN CLASIFICAR excluye todos los valores REALES de
        # los demás atributos.
        #
        # Con esto se permiten:
        #
        # Blanco / S
        # Negro / M
        # SIN CLASIFICAR / SIN CLASIFICAR
        #
        # Pero no:
        #
        # SIN CLASIFICAR / S
        # Blanco / SIN CLASIFICAR
        # --------------------------------------------------------
        exclusions_to_create = []

        for technical_ptav in technical_ptavs:

            other_real_ptavs = (
                variant_lines.product_template_value_ids - technical_ptavs
            ).filtered(
                lambda ptav: (
                    ptav.attribute_line_id != technical_ptav.attribute_line_id
                )
            )

            existing_exclusion = Exclusion.search(
                [
                    ("product_tmpl_id", "=", self.id),
                    (
                        "product_template_attribute_value_id",
                        "=",
                        technical_ptav.id,
                    ),
                ],
                limit=1,
            )

            if existing_exclusion:
                existing_exclusion.write(
                    {
                        "value_ids": [(6, 0, other_real_ptavs.ids)],
                    }
                )
            else:
                exclusions_to_create.append(
                    {
                        "product_tmpl_id": self.id,
                        "product_template_attribute_value_id": technical_ptav.id,
                        "value_ids": [(6, 0, other_real_ptavs.ids)],
                    }
                )

        if exclusions_to_create:
            Exclusion.create(exclusions_to_create)

        # --------------------------------------------------------
        # 4. Identificar la única variante formada completamente
        #    por valores SIN CLASIFICAR.
        # --------------------------------------------------------
        technical_ids = set(technical_ptavs.ids)

        technical_variant = self.product_variant_ids.filtered(
            lambda product: (
                set(product.product_template_attribute_value_ids.ids) == technical_ids
            )
        )

        if len(technical_variant) != 1:
            raise UserError(
                "No se pudo generar una única variante técnica "
                "SIN CLASIFICAR para este producto."
            )

        # --------------------------------------------------------
        # 5. Garantizar que únicamente esa variante quede marcada.
        # --------------------------------------------------------
        all_variants = self.with_context(active_test=False).product_variant_ids

        previously_marked = all_variants.filtered(
            lambda product: (
                product.is_unclassified_variant and product != technical_variant
            )
        )

        if previously_marked:
            previously_marked.write(
                {
                    "is_unclassified_variant": False,
                }
            )

        technical_variant.write(
            {
                "is_unclassified_variant": True,
            }
        )

        return technical_variant
