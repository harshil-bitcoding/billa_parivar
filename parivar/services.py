import csv
import io
import os
import openpyxl
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from .models import Surname, Person, District, Taluka, Village

class LocationResolverService:
    @staticmethod
    def resolve_location(district_name, taluka_name, village_name):
        """
        Resolves hierarchical location (District -> Taluka -> Village).
        Instead of mismatch blocking, it creates a new record if not found under the parent.
        returns: (village_obj, status)
        status: "exact" | "created"
        """
        # 1. Resolve District
        district_name = str(district_name).strip()
        district = District.objects.filter(name__iexact=district_name).first()
        dist_status = "exact"
        if not district:
            district = District.objects.create(name=district_name)
            dist_status = "created"

        # 2. Resolve Taluka
        taluka_name = str(taluka_name).strip()
        # Look for taluka specifically within this district
        taluka = Taluka.objects.filter(name__iexact=taluka_name, district=district).first()
        tal_status = "exact"
        if not taluka:
            taluka = Taluka.objects.create(name=taluka_name, district=district)
            tal_status = "created"

        # 3. Resolve Village
        village_name = str(village_name).strip()
        # Look for village specifically within this taluka
        village = Village.objects.filter(name__iexact=village_name, taluka=taluka).first()
        vil_status = "exact"
        if not village:
            village = Village.objects.create(name=village_name, taluka=taluka)
            vil_status = "created"
        
        # Decide final status
        final_status = "exact"
        if dist_status == "created" or tal_status == "created" or vil_status == "created":
            final_status = "created"

        return village, final_status

class CSVImportService:
    @staticmethod
    def clean_val(val):
        if not val:
            return ""
        val = str(val).strip()
        # Remove Excel formula wrapper ="value"
        if val.startswith('="') and val.endswith('"'):
            return val[2:-1]
        # Remove single quote prefix
        if val.startswith("'"):
            return val[1:]
        return val

    @classmethod
    def process_file(cls, uploaded_file, request=None):
        """
        Core logic for processing CSV/XLSX files.
        Returns a dictionary with results.
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
        for sheet_name, rows in all_sheets_data.items():
            if not rows: continue
            
            header_row_idx = -1
            col_map = {}
            is_dashboard = False
            
            if sheet_name.lower() in ['dashbord', 'dashboard']:
                is_dashboard = True

            keywords = {
                'first_name': ['Firstname', 'First name', 'First Name'],
                'middle_name': ['Father name', 'Father Name'],
                'surname': ['Surname', 'Sirname'],
                'mobile1': ['Mobile Number', 'Mobile Number Main', 'Main'],
                'district': ['District'],
                'taluka': ['Taluka'],
                'village': ['Village'],
                'referral_code': ['Reference Code', 'Referral Code'],
                'father_name': ['Name of Father'],
                'son_name': ['Name of Son'],
            }

            for i in range(min(10, len(rows))):
                row_str = [str(c).strip().lower() if c else "" for c in rows[i]]
                if any(k.lower() in " ".join(row_str) for k in ['firstname', 'surname', 'mobile', 'district', 'village']):
                    header_row_idx = i
                    for j, cell in enumerate(rows[i]):
                        cell_val = str(cell).strip() if cell else ""
                        for key, keys in keywords.items():
                            if any(k.lower() in cell_val.lower() for k in keys):
                                col_map[key] = j
                    break
            
            if header_row_idx == -1:
                if is_dashboard:
                    bug_rows.append([sheet_name, "N/A", "Header not detected in Dashboard sheet"])
                continue

            start_row = header_row_idx + 1
            for idx, row in enumerate(rows[start_row:]):
                if not any(row): continue
                
                try:
                    d_name = cls.clean_val(row[col_map['district']]) if 'district' in col_map else ""
                    t_name = cls.clean_val(row[col_map['taluka']]) if 'taluka' in col_map else ""
                    v_name = cls.clean_val(row[col_map['village']]) if 'village' in col_map else ""
                    
                    if not (d_name and t_name and v_name):
                        bug_rows.append(list(row) + [f"Missing location columns in sheet {sheet_name}"])
                        continue

                    village_obj, _ = LocationResolverService.resolve_location(d_name, t_name, v_name)
                    
                    if is_dashboard:
                        ref_code = cls.clean_val(row[col_map['referral_code']]) if 'referral_code' in col_map else ""
                        if village_obj and ref_code:
                            village_obj.referral_code = ref_code
                            village_obj.save()
                            total_updated += 1
                        continue
                    
                    f_name = cls.clean_val(row[col_map['first_name']]) if 'first_name' in col_map else ""
                    mob1 = cls.clean_val(row[col_map['mobile1']]) if 'mobile1' in col_map else ""
                    s_name = cls.clean_val(row[col_map['surname']]) if 'surname' in col_map else ""
                    
                    if f_name and mob1:
                        surname_obj, _ = Surname.objects.get_or_create(name=s_name) if s_name else (None, False)
                        
                        person_defaults = {
                            'first_name': f_name,
                            'surname': surname_obj,
                            'village': village_obj,
                            'taluka': village_obj.taluka if village_obj else None,
                            'district': village_obj.taluka.district if village_obj and village_obj.taluka else None,
                            'flag_show': True
                        }
                        
                        person, created = Person.objects.update_or_create(
                            mobile_number1=mob1, is_deleted=False, defaults=person_defaults
                        )
                        if created: total_created += 1
                        else: total_updated += 1
                except Exception as e:
                    bug_rows.append(list(row) + [str(e)])

        # 4. Generate Bug CSV if needed
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
