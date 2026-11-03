import json
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestInterventionApi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env, login="api_manager", password="api_manager_pwd",
            groups="base.group_user,intervention_management.group_intervention_manager",
        )
        partner = cls.env["res.partner"].create({"name": "Client API"})
        tech = cls.env["intervention.technician"].create({"name": "Tech API"})
        Intervention = cls.env["intervention.intervention"]
        cls.planned = Intervention.create({
            "partner_id": partner.id, "technician_id": tech.id,
            "date_planned": fields.Datetime.now() + timedelta(days=2),
        })
        cls.planned.action_plan()
        Intervention.create({"partner_id": partner.id})

    def test_authentification_obligatoire(self):
        response = self.url_open("/api/interventions/stats", allow_redirects=False)
        self.assertIn(response.status_code, (302, 303, 401, 403))

    def test_liste_filtree(self):
        self.authenticate("api_manager", "api_manager_pwd")
        data = json.loads(self.url_open("/api/interventions?state=planned").content)
        references = [item["reference"] for item in data["items"]]
        self.assertIn(self.planned.name, references)
        self.assertTrue(all(item["state"] == "planned" for item in data["items"]))

    def test_etat_invalide(self):
        self.authenticate("api_manager", "api_manager_pwd")
        self.assertEqual(self.url_open("/api/interventions?state=foo").status_code, 400)

    def test_statistiques(self):
        self.authenticate("api_manager", "api_manager_pwd")
        data = json.loads(self.url_open("/api/interventions/stats").content)
        self.assertGreaterEqual(data["by_state"]["planned"], 1)
        self.assertGreaterEqual(data["by_state"]["draft"], 1)
        self.assertIn(self.planned.name, [i["reference"] for i in data["upcoming"]])
        self.assertIn("Tech API", [t["name"] for t in data["by_technician"]])
