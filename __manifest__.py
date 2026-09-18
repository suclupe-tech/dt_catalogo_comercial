# -*- coding: utf-8 -*-

{
    "name": "Detalles Textiles - Catálogo Comercial",
    "version": "19.0.1.0.0",
    "category": "Inventory",
    "summary": "Catálogo comercial y control de productos por modelo o variante",
    "description": """
Detalles Textiles - Catálogo Comercial
======================================

Módulo base para la nueva arquitectura comercial de Detalles Textiles S.A.C.

Objetivos iniciales:
- Configurar almacenes con control por MODELO o VARIANTE.
- Extender el catálogo de productos con información comercial.
- Preparar la base para canales físico, mayorista y digital.
- Mantener un único producto maestro.
- Evitar duplicidades por ONLINE, OFERTA u otros canales.
- Preparar futuras transferencias adaptativas entre almacenes.
    """,
    "author": "Detalles Textiles S.A.C.",
    "license": "LGPL-3",
    # Dependencias mínimas para esta primera fase.
    # Todavía no añadimos POS ni Ventas para mantener
    # el módulo base desacoplado.
    "depends": [
        "product",
        "stock",
        "mail",
        "pos_stock_restriccion_tienda",
    ],
    "data": [
        "security/commercial_offer_security.xml",
        "security/ir.model.access.csv",
        "views/stock_warehouse_views.xml",
        "views/product_template_views.xml",
        "views/stock_commercial_allocation_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
