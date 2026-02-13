import os
import django
import json
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bila_parivar.settings')
django.setup()

from demo.models import DemoPerson, DemoParentChildRelation, DemoSurname
from parivar.serializers import PersonGetSerializer
from parivar.v4.views import V4RelationtreeAPIView
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

def verify_tree():
    print("Verifying Relation Tree Data for Demo Mode...")

    # 1. Get a DemoPerson to test with (preferably a top member or someone with relations)
    # Try to find a person who is a parent in some relation
    relation = DemoParentChildRelation.objects.first()
    if not relation:
        print("No DemoParentChildRelation found! Cannot verify tree.")
        return

    person_id = relation.parent.id
    print(f"Testing with DemoPerson ID: {person_id} (Found from relation)")

    # 2. Simulate View Logic (extracted from V4RelationtreeAPIView)
    try:
        person = DemoPerson.objects.get(id=person_id)
        if not person.surname:
             print("Person has no surname, skipping.")
             return

        surname_id = person.surname.id
        print(f"Person Surname ID: {surname_id}")
        
        # In the view fix, we used: surname_obj = DemoSurname.objects.get(id=surname)
        surname_obj = DemoSurname.objects.get(id=surname_id)
        topmember = surname_obj.top_member
        print(f"Top Member ID: {topmember.id if topmember else 'None'}")

        # Initialize relations
        relations = DemoParentChildRelation.objects.filter(child_id=person_id)
        parent_data_id = {int(person_id)}

        print(f"Initial relations count: {relations.count()}")

        # Traverse up the tree
        while relations:
            new_relations = []
            for relation in relations:
                parent_id = relation.parent.id
                # Check for recursion/top member
                if topmember and str(parent_id) == str(topmember.id):
                    break
                
                if int(parent_id) not in parent_data_id:
                    parent_data_id.add(int(parent_id))
                    # Fetch next level up
                    new_relations.extend(
                        DemoParentChildRelation.objects.filter(child_id=parent_id)
                    )
            relations = new_relations
        
        print(f"Collected Parent IDs: {parent_data_id}")

        # Fetch all family members in the tree path
        person_data = (
            DemoPerson.objects.filter(
                surname__id=surname_id, flag_show=True
            )
            .exclude(id__in=parent_data_id)
            .order_by("first_name")
        )
        
        print(f"Found {person_data.count()} family members to display.")

        # 3. Serialize
        print("Serializing data...")
        serializer = PersonGetSerializer(
            person_data, many=True, context={"lang": "en", "is_demo": True}
        )
        
        data = serializer.data
        print(f"Successfully serialized {len(data)} records.")
        
        if len(data) > 0:
            print("Sample Record (First 1):")
            print(json.dumps(data[0], indent=2, default=str))
        else:
            print("No data serialized.")

    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_tree()
