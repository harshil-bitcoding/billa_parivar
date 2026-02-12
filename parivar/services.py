import csv
import io
import os
import openpyxl
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from .models import Surname, Person, District, Taluka, Village, Country

class LocationResolverService:
    @staticmethod
    def resolve_location(district_name, taluka_name, village_name):
        """
        Resolves hierarchical location (District -> Taluka -> Village).
        Strict policy: Returns None if match not found.
        Matching is case-insensitive.
        """
        # 1. Resolve District
        district_name = str(district_name).strip()
        district = District.objects.filter(name__iexact=district_name).first()
        if not district:
            return None, f"District Not Found: '{district_name}'"

        # 2. Resolve Taluka
        taluka_name = str(taluka_name).strip()
        taluka = Taluka.objects.filter(name__iexact=taluka_name, district=district).first()
        if not taluka:
            return None, f"Taluka Not Found: '{taluka_name}' (in District: {district_name})"

        # 3. Resolve Village
        village_name = str(village_name).strip()
        village = Village.objects.filter(name__iexact=village_name, taluka=taluka).first()
        if not village:
            return None, f"Village Not Found: '{village_name}' (in Taluka: {taluka_name})"
        
        return village, "exact"

class CSVImportService:
    @staticmethod
    def clean_val(val):
        if val is None:
            return ""
        val = str(val).strip()
        # Remove Excel formula wrapper ="value"
        if val.startswith('="') and val.endswith('"'):
            return val[2:-1]
        # Remove single quote prefix
        if val.startswith("'"):
            return val[1:]
        return val

    @staticmethod
    def resolve_surname(name):
        """
        Policy:
        Compare sheet data and DB data in the same case.
        If a case-insensitive match exists, use it to avoid unnecessary bug files.
        """
        name = str(name).strip()
        if not name:
            return None, "empty"
        
        # Use Case-insensitive match (PostgreSQL iexact handles "same case" comparison)
        obj = Surname.objects.filter(name__iexact=name).first()
        if obj:
            # Match found (e.g. "Patel" for "patel") - use it.
            return obj, "exact"
        
        # No match at all - create new
        new_surname = Surname.objects.create(name=name)
        return new_surname, "created"

    @classmethod
    def process_file(cls, uploaded_file, request=None):
        """
        Core logic for processing CSV/XLSX files.
        Mirrored from DemoCSVUploadAPIView with added surname policy.
        """
        # 1. Save original file
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads', 'original'))
        filename = fs.save(uploaded_file.name, uploaded_file)
        
        # Rewind file for processing
        uploaded_file.seek(0)
        
        ext = uploaded_file.name.lower().split('.')[-1]
        all_sheets_data = {}

        # 2. Extract Data
        if ext in ['xlsx', 'xls']:
            try:
                wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    rows = []
                    for row in sheet.iter_rows(values_only=True):
                        rows.append(list(row))
                    all_sheets_data[sheet_name] = rows
            except Exception as e:
                return {"error": f"Failed to read XLSX: {str(e)}"}
        else:
            try:
                file_data = uploaded_file.read()
                try:
                    decoded = file_data.decode('utf-8-sig')
                except:
                    decoded = file_data.decode('latin-1')
                normalized = "\n".join(decoded.splitlines())
                reader = csv.reader(io.StringIO(normalized))
                rows = [row for row in reader]
                all_sheets_data['default'] = rows
            except Exception as e:
                return {"error": f"Failed to read CSV: {str(e)}"}

        total_created = 0
        total_updated = 0
        bug_rows = []
        
        # 3. Process Sheets
        global_village = None
        global_d_name, global_t_name, global_v_name = "", "", ""

        for s_idx, (sheet_name, rows) in enumerate(all_sheets_data.items()):
            # 3. Tab Processing Policy
            if s_idx == 0: # 1st Tab: Dashboard
                header_row_idx = -1
                for i in range(min(5, len(rows))):
                    row_str = " ".join([str(c) for c in rows[i] if c]).lower()
                    if 'district' in row_str and 'village' in row_str:
                        header_row_idx = i
                        break
                
                if header_row_idx != -1 and len(rows) > header_row_idx + 1:
                    data_row = rows[header_row_idx + 1]
                    # Assuming standard layout for Dashboard: District (0), Taluka (1), Village (2), RefCode (3)
                    global_d_name = cls.clean_val(data_row[0]) if len(data_row) > 0 else ""
                    global_t_name = cls.clean_val(data_row[1]) if len(data_row) > 1 else ""
                    global_v_name = cls.clean_val(data_row[2]) if len(data_row) > 2 else ""
                    
                    global_village, loc_status = LocationResolverService.resolve_location(global_d_name, global_t_name, global_v_name)
                    if not global_village:
                        return {"error": f"Dashboard Location Error: {loc_status} for {global_d_name}/{global_t_name}/{global_v_name}"}
                    
                    # Update Referral Code
                    ref_code = cls.clean_val(data_row[3]) if len(data_row) > 3 else ""
                    if ref_code:
                        global_village.referral_code = ref_code
                        global_village.save()
                continue

            if s_idx == 1: # 2nd Tab: Dummy
                continue

            # 3rd Tab & Onwards: Person Data
            if not global_village:
                continue

            col_map = {}
            keywords = {
                'first_name': ['Firstname (In English)', 'Firstname', 'First name'],
                'guj_first_name': ['Firstname (In Gujarati)', 'In Gujarati'],
                'middle_name': ['Father name (In English)', 'Father name', 'Name of Father'],
                'guj_middle_name': ['Father name (In Gujarati)', 'Father name Gujarati'],
                'surname': ['Surname', 'Sirname'],
                'mobile1': ['Mobile Number Main', 'Main', 'Mobile'],
                'mobile2': ['Mobile Number (Optional)', 'Secondary', 'Optional'],
                'dob': ['Birth Date', 'Birt Date', 'DOB'],
                'country': ['Country Name', 'Outside India', 'Country'],
                'int_mobile': ['International Mobile', 'International'],
            }

            # Smart Header Detection
            header_row_idx = -1
            for i in range(min(10, len(rows))):
                row = [str(c).strip() if c else "" for c in rows[i]]
                row_str = " ".join(row).lower()
                if any(x in row_str for x in ['firstname', 'surname', 'mobile']):
                    header_row_idx = i
                    for j, cell in enumerate(row):
                        cell_val = str(cell).strip()
                        next_cell_val = ""
                        if i + 1 < len(rows) and j < len(rows[i+1]):
                            next_cell_val = str(rows[i+1][j]).strip() if rows[i+1][j] else ""
                        combined_col_str = f"{cell_val} {next_cell_val}"

                        for key, keys in keywords.items():
                            if any(k.lower() in combined_col_str.lower() for k in keys):
                                if key == 'mobile1':
                                    if "Main" in combined_col_str: col_map['mobile1'] = j
                                    elif "Optional" in combined_col_str: col_map['mobile2'] = j
                                    elif 'mobile1' not in col_map: col_map['mobile1'] = j
                                else:
                                    if any(k.lower() == combined_col_str.strip().lower() for k in keys):
                                        col_map[key] = j
                                    elif key not in col_map:
                                        col_map[key] = j
                    break

            if header_row_idx == -1:
                continue

            start_row = header_row_idx + 1
            if start_row < len(rows):
                sub_row_str = " ".join([str(x) for x in rows[start_row]]).lower()
                if any(x in sub_row_str for x in ["english", "gujarati", "main", "optional"]):
                    start_row += 1

            for idx, row in enumerate(rows[start_row:]):
                if not any(row): continue
                
                try:
                    # Person Data Extraction
                    f_name = cls.clean_val(row[col_map['first_name']]) if 'first_name' in col_map else ""
                    m_name = cls.clean_val(row[col_map['middle_name']]) if 'middle_name' in col_map else ""
                    guj_f_name = cls.clean_val(row[col_map['guj_first_name']]) if 'guj_first_name' in col_map else ""
                    guj_m_name = cls.clean_val(row[col_map['guj_middle_name']]) if 'guj_middle_name' in col_map else ""
                    s_name = cls.clean_val(row[col_map['surname']]) if 'surname' in col_map else ""
                    mob1 = cls.clean_val(row[col_map['mobile1']]) if 'mobile1' in col_map else ""
                    mob2 = cls.clean_val(row[col_map['mobile2']]) if 'mobile2' in col_map else ""
                    dob_raw = cls.clean_val(row[col_map['dob']]) if 'dob' in col_map else ""
                    country_name = cls.clean_val(row[col_map['country']]) if 'country' in col_map else ""
                    int_mob = cls.clean_val(row[col_map['int_mobile']]) if 'int_mobile' in col_map else ""
                    
                    # Skip only if the entire row is empty (ignore formatting/spacing)
                    if not any([f_name, m_name, guj_f_name, guj_m_name, s_name, mob1, mob2, dob_raw, country_name, int_mob]):
                        continue

                    # Surname Matching (Case-Insensitive)
                    surname_obj = None
                    if s_name:
                        surname_obj, _ = cls.resolve_surname(s_name)

                    # DOB Normalization
                    dob = str(dob_raw).strip() if dob_raw else ""
                    if dob:
                        # Handle YYYY-MM-DD HH:MM:SS (common in Excel/openpyxl)
                        if ' ' in dob:
                            dob = dob.split(' ')[0]
                        
                        if '-' in dob:
                            parts = dob.split('-')
                            if len(parts) == 3 and len(parts[0]) == 4: # YYYY-MM-DD
                                dob = f"{parts[2]}-{parts[1]}-{parts[0]}"

                    # Country Handling
                    c_name = country_name if country_name else "India"
                    country_obj, _ = Country.objects.get_or_create(name=c_name)
                    is_out = country_obj.name.lower() != 'india'

                    person_defaults = {
                        'first_name': f_name,
                        'middle_name': m_name,
                        'guj_first_name': guj_f_name,
                        'guj_middle_name': guj_m_name,
                        'surname': surname_obj,
                        'date_of_birth': dob,
                        'mobile_number2': mob2,
                        'is_out_of_country': is_out,
                        'out_of_country': country_obj,
                        'international_mobile_number': int_mob,
                        'village': global_village,
                        'taluka': global_village.taluka if global_village else None,
                        'district': global_village.taluka.district if global_village and global_village.taluka else None,
                        'flag_show': True
                    }
                    
                    if mob1:
                        # Update or create if mobile is present
                        person, created = Person.objects.update_or_create(
                            mobile_number1=mob1, is_deleted=False, defaults=person_defaults
                        )
                    else:
                        # Missing mobile: Always create new to avoid merging different people
                        person_defaults['mobile_number1'] = mob1
                        person = Person.objects.create(**person_defaults)
                        created = True

                    if created: total_created += 1
                    else: total_updated += 1
                except Exception as e:
                    bug_rows.append(list(row) + [str(e)])

        # 4. Process Relations (Name-based) - Mirrored from Demo
        from .models import ParentChildRelation
        system_admin = Person.objects.filter(is_super_admin=True).first()
        if not system_admin:
            system_admin = Person.objects.filter(is_admin=True).first()
        
        if system_admin:
            # Mirror the Demo logic: check all persons for potential father matches
            all_persons = Person.objects.filter(is_deleted=False).select_related('surname')
            for child in all_persons:
                father_name = child.middle_name
                if father_name and child.surname:
                    father = Person.objects.filter(
                        first_name__iexact=father_name,
                        surname=child.surname,
                        is_deleted=False
                    ).exclude(id=child.id).first()
                    if father:
                        ParentChildRelation.objects.get_or_create(
                            parent=father, 
                            child=child,
                            defaults={'created_user': system_admin}
                        )

        # 5. Generate Bug CSV if needed
        bug_url = None
        if bug_rows:
            bug_fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads', 'bugs'))
            bug_filename = f"bug_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Row Data", "Error Message"])
            for bug in bug_rows:
                writer.writerow(bug)
            
            bug_fs.save(bug_filename, io.BytesIO(output.getvalue().encode('utf-8')))
            
            if request:
                bug_url = request.build_absolute_uri(settings.MEDIA_URL + f"uploads/bugs/{bug_filename}")
            else:
                bug_url = settings.MEDIA_URL + f"uploads/bugs/{bug_filename}"

        return {
            "created": total_created,
            "updated": total_updated,
            "bug_file_url": bug_url,
            "bug_count": len(bug_rows),
            "original_filename": filename
        }
