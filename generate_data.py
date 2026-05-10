import os
import random

DATA_DIR = "/Users/huseyintamer/Documents/AI CV/Assesment/data"
os.makedirs(DATA_DIR, exist_ok=True)

def generate_file(filename, doc_name, classification, department, num_articles, paragraphs_per_article):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w") as f:
        f.write(f"DOCUMENT: {doc_name}\n")
        f.write(f"CLASSIFICATION: {classification}\n")
        f.write(f"DEPARTMENT: {department}\n\n")
        
        for art in range(1, num_articles + 1):
            f.write(f"--- ARTICLE {art} ---\n")
            for para in range(1, paragraphs_per_article + 1):
                # Generate department-specific legal text
                year = random.choice([2024, 2025, 2026])
                if department == "FIOD":
                    text = f"The investigation regarding entity {random.randint(1000, 9999)} reveals transaction anomalies in fiscal period {year}. Subject failed to declare offshore assets totaling {random.randint(100000, 5000000)} EUR. Seizure of assets is authorized under section {random.randint(1, 100)}."
                elif department == "International":
                    text = f"Under the bilateral treaty framework established in {year}, withholding tax on dividends distributed to non-resident entities shall be capped at {random.choice([5, 10, 15])}%. This applies exclusively to entities holding at least {random.choice([10, 25])}% of capital."
                else:
                    text = f"For the fiscal year {year}, any corporate entity engaging in activities defined under the Schedule {random.choice(['A', 'B', 'C'])} must adhere to the standard reporting guidelines. Deductions for depreciation of capital assets are limited to {random.randint(10, 30)}% per annum."
                
                # Add heavy padding to make the files massive
                padding = " ".join([
                    f"Furthermore, pursuant to statutory requirements, subsection {i} mandates strict adherence to the compliance frameworks governing {department} operations, overriding any prior informal arrangements." 
                    for i in range(1, 15)
                ])
                
                f.write(f"Paragraph {para}: {text} {padding}\n")
            f.write("\n")

def main():
    files_to_generate = [
        ("tax_code_2025.txt", "Wet op de Vennootschapsbelasting 2025", "Public", "Tax Policy", 100, 10),
        ("fiod_report_project_x.txt", "FIOD Investigation Report - Project X", "Secret", "FIOD", 50, 15),
        ("treaty_nl_us_2026.txt", "Bilateral Tax Treaty NL-US 2026", "Public", "International", 80, 8),
        ("fiod_audit_mega_corp.txt", "FIOD Audit - MegaCorp Holdings", "Secret", "FIOD", 60, 20),
        ("customs_regulations_2024.txt", "Customs Tariff Schedule 2024", "Public", "Customs", 120, 5),
        ("corporate_audit_guidelines.txt", "Corporate Audit Standards v4", "Confidential", "Corporate Audit", 70, 10),
        ("environmental_tax_act.txt", "Environmental Levy Act 2025", "Public", "Tax Policy", 90, 6),
        ("fiod_money_laundering.txt", "FIOD AML Typologies 2026", "Restricted", "FIOD", 50, 12),
        ("treaty_nl_uk_2025.txt", "Bilateral Tax Treaty NL-UK 2025", "Public", "International", 80, 8),
        ("digital_services_tax_2026.txt", "Digital Services Tax Directive 2026", "Confidential", "Tax Policy", 100, 7)
    ]
    
    for meta in files_to_generate:
        generate_file(*meta)
        print(f"Generated: {meta[0]} ({meta[4] * meta[5]} paragraphs)")

if __name__ == "__main__":
    main()
