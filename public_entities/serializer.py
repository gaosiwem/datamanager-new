from rest_framework.serializers import ModelSerializer
from .models import PublicEntity
from budgetportal.models.government import Department, Government, Sphere, FinancialYear


class FinancialYearSerializer(ModelSerializer):
    class Meta:
        model = FinancialYear
        fields = ("slug",)


class SphereSerializer(ModelSerializer):
    financial_year = FinancialYearSerializer()

    class Meta:
        model = Sphere
        fields = (
            "financial_year",
            "name",
        )


class GovernmentSerializer(ModelSerializer):
    sphere = SphereSerializer()

    class Meta:
        model = Government
        fields = (
            "sphere",
            "name",
        )


class DepartmentSerializer(ModelSerializer):
    government = GovernmentSerializer()

    class Meta:
        model = Department
        fields = (
            "government",
            "name",
        )


class PublicEntitiesSerializer(ModelSerializer):
    department = DepartmentSerializer()

    class Meta:
        model = PublicEntity        
        fields = '__all__'
