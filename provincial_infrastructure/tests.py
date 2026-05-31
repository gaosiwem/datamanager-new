# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from budgetportal.models import InfraProject
from django.test import SimpleTestCase

from provincial_infrastructure.views import InfraProjectSearchView


class InfraProjectSearchViewTestCase(SimpleTestCase):
    def test_search_view_is_scoped_to_infrastructure_projects(self):
        self.assertEqual(InfraProjectSearchView.index_models, [InfraProject])
