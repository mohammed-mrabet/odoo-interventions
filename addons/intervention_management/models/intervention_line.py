from odoo import api, fields, models


class InterventionLine(models.Model):
    _name = "intervention.line"
    _description = "Matériel utilisé lors d'une intervention"

    intervention_id = fields.Many2one("intervention.intervention", required=True, ondelete="cascade")
    name = fields.Char(string="Article", required=True)
    quantity = fields.Float(string="Quantité", default=1.0)
    price_unit = fields.Monetary(string="Prix unitaire")
    currency_id = fields.Many2one(related="intervention_id.currency_id")
    subtotal = fields.Monetary(string="Sous-total", compute="_compute_subtotal", store=True)

    _sql_constraints = [
        ("quantity_positive", "CHECK(quantity > 0)", "La quantité doit être positive."),
        ("price_positive", "CHECK(price_unit >= 0)", "Le prix ne peut pas être négatif."),
    ]

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
