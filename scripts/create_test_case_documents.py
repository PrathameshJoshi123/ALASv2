"""
Generate authentic, realistic Indian legal test case PDF files
for Case File Analysis & Pre-Trial Intelligence.

Matter:
State (NCT of Delhi) & Apex FinTech Innovations Ltd. vs. Zenith Cloud Technologies Pvt. Ltd. & Ors.
FIR No. 0412/2024 (PS Mandir Marg / EOW New Delhi)
"""

import os
from pathlib import Path
import pypdf

OUTPUT_DIR = Path("backend/storage/dummy_cases/apex_vs_zenith")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_raw_pdf(lines: list[str], output_path: Path):
    """
    Build a standard compliant PDF 1.4 document in pure Python with no external dependencies.
    """
    # Break lines into pages (~45 lines per page)
    lines_per_page = 42
    pages_lines = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
    if not pages_lines:
        pages_lines = [[""]]

    num_pages = len(pages_lines)
    
    # We will generate objects:
    # 1: Catalog
    # 2: Pages
    # 3 to 2+num_pages: Page objects
    # 3+num_pages to 2+2*num_pages: Content stream objects
    # font object: 3 + 2*num_pages
    
    font_obj_id = 3 + 2 * num_pages
    page_obj_ids = [3 + i for i in range(num_pages)]
    content_obj_ids = [3 + num_pages + i for i in range(num_pages)]
    
    objects = {}
    
    # Catalog
    objects[1] = f"<< /Type /Catalog /Pages 2 0 R >>\n".encode("latin1")
    
    # Pages
    kids_str = " ".join([f"{pid} 0 R" for pid in page_obj_ids])
    objects[2] = f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>\n".encode("latin1")
    
    # Font
    objects[font_obj_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
    
    # Each Page and its Content stream
    for idx, page_lines in enumerate(pages_lines):
        pid = page_obj_ids[idx]
        cid = content_obj_ids[idx]
        
        objects[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {cid} 0 R /Resources << /Font << /F1 {font_obj_id} 0 R >> >> >>\n"
        ).encode("latin1")
        
        # Build stream text
        stream = "BT /F1 9 Tf 40 750 Td 13.5 TL "
        for l in page_lines:
            safe = (
                l.replace("\\", "\\\\")
                .replace("(", "\\(")
                .replace(")", "\\)")
            )
            stream += f"({safe}) ' "
        stream += "ET"
        stream_bytes = stream.encode("latin1", errors="replace")
        
        objects[cid] = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin1")
            + stream_bytes
            + b"\nendstream\n"
        )
        
    # Assemble PDF with cross-reference table
    header = b"%PDF-1.4\n"
    body = bytearray(header)
    offsets = {}
    
    sorted_ids = sorted(objects.keys())
    for oid in sorted_ids:
        offsets[oid] = len(body)
        body.extend(f"{oid} 0 obj\n".encode("latin1"))
        body.extend(objects[oid])
        body.extend(b"endobj\n")
        
    xref_pos = len(body)
    total_objs = max(sorted_ids) + 1
    xref_str = f"xref\n0 {total_objs}\n0000000000 65535 f \n"
    for oid in range(1, total_objs):
        if oid in offsets:
            xref_str += f"{offsets[oid]:010d} 00000 n \n"
        else:
            xref_str += "0000000000 00000 f \n"
            
    trailer_str = (
        f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    )
    
    body.extend(xref_str.encode("latin1"))
    body.extend(trailer_str.encode("latin1"))
    
    with open(output_path, "wb") as f:
        f.write(body)
        
    print(f"Generated {output_path} ({len(body)} bytes, {num_pages} pages)")


def generate_all_case_documents():
    # 1. FIR Document
    fir_lines = [
        "FIRST INFORMATION REPORT (Under Section 154 Cr.P.C. / Section 173 BNSS, 2023)",
        "POLICE STATION: Economic Offences Wing (EOW), Mandir Marg, New Delhi",
        "DISTRICT: New Delhi | YEAR: 2024 | FIR NO: 0412/2024 | DATE & TIME: 14/08/2024 at 11:30 AM",
        "--------------------------------------------------------------------------------",
        "1. ACTS & STATUTORY SECTIONS CITED:",
        "   (a) Section 420 Indian Penal Code (Cheating & Dishonestly Inducing Delivery of Property)",
        "   (b) Section 406 Indian Penal Code (Criminal Breach of Trust)",
        "   (c) Section 468 & 471 Indian Penal Code (Forgery for Purpose of Cheating & Using Forged Document)",
        "   (d) Section 120-B Indian Penal Code (Criminal Conspiracy)",
        "--------------------------------------------------------------------------------",
        "2. COMPLAINANT INFORMATION:",
        "   Name: Mr. Vikramaditya Singhania, Managing Director, Apex FinTech Innovations Ltd.",
        "   Registered Office: Cyber City, Tower B, Level 14, Gurugram, NCR.",
        "--------------------------------------------------------------------------------",
        "3. ACCUSED PERSONS:",
        "   Accused No. 1: Rajesh Malhotra, Managing Director, Zenith Cloud Technologies Pvt. Ltd.",
        "   Accused No. 2: Sameer Verma, Chief Technical Officer, Zenith Cloud Technologies Pvt. Ltd.",
        "   Accused No. 3: M/s Zenith Cloud Technologies Pvt. Ltd., Okhla Industrial Area Ph-III, New Delhi.",
        "--------------------------------------------------------------------------------",
        "4. STATEMENT OF FACTS AND ALLEGATIONS:",
        "The Complainant company entered into a Master Software Deployment and Escrow Agreement on 15/01/2024",
        "with Zenith Cloud Technologies Pvt. Ltd. for implementing a high-throughput algorithmic core clearing engine.",
        "The total agreed contractual consideration was INR 8,50,00,000/- (Eight Crores Fifty Lakhs Only).",
        "Under Clause 3.2 of the agreement, Complainant released Milestone Tranche-1 of INR 4,25,00,000/- on 05/02/2024.",
        "This disbursement was made strictly upon Accused No. 1 and 2 furnishing an ISO/IEC 27001 Security Audit",
        "Certificate and Third-Party Escrow Confirmation purportedly issued by CertiGuard Labs Singapore on 04/02/2024.",
        "",
        "In July 2024, when milestone delivery was overdue, an internal technical audit revealed that CertiGuard Labs",
        "was a fictitious entity registered in Delaware by a close relative of Accused No. 1.",
        "No proprietary source code was ever deposited into the independent third-party escrow repository.",
        "Bank verification revealed that within 48 hours of credit, INR 4,10,00,000/- was systematically diverted",
        "to personal demat accounts and an affiliated real estate shell company, Malhotra Ventures LLP.",
        "On 10/08/2024, when Complainant visited the Okhla premises to demand inspection of code, Accused No. 1",
        "physically assaulted Complainant's officers, threatened them with criminal intimidation, and bolted the premises.",
        "",
        "5. PRIMA FACIE FINDINGS OF INVESTIGATING OFFICER:",
        "The accused persons dishonestly induced the complainant to part with INR 4,25,00,000/- using forged credentials.",
        "Ingredients of cheating under Section 420 IPC and criminal breach of trust under Section 406 IPC are attracted.",
        "Investigation endorsed to SI Devendra Chawla, EOW Mandir Marg.",
        "Sd/- Inspector Devendra Chawla, Investigating Officer (EOW Delhi Police)."
    ]
    build_raw_pdf(fir_lines, OUTPUT_DIR / "01_FIR_0412_2024_Mandir_Marg.pdf")

    # 2. PW-1 Statement under Section 161 CrPC
    pw1_lines = [
        "STATEMENT OF WITNESS UNDER SECTION 161 Cr.P.C. / SECTION 180 BNSS, 2023",
        "POLICE STATION: EOW, Mandir Marg, New Delhi | FIR NO: 0412/2024",
        "DATE OF EXAMINATION: 18/08/2024 | INVESTIGATING OFFICER: SI Devendra Chawla",
        "--------------------------------------------------------------------------------",
        "WITNESS IDENTIFICATION:",
        "Name: Ramesh Gupta, S/o Late K. L. Gupta, Age: 44 Years",
        "Designation: Chief Financial Officer, Apex FinTech Innovations Ltd., Gurugram.",
        "--------------------------------------------------------------------------------",
        "WITNESS TESTIMONY:",
        "I am the Chief Financial Officer of Apex FinTech Innovations Ltd. since January 2021.",
        "I was personally involved in negotiating the financial terms of the Master Agreement dated 15/01/2024.",
        "On 04/02/2024, Accused No. 2 Sameer Verma emailed the CertiGuard escrow receipt to my corporate email address.",
        "I verified the email attachment and authorized the RTGS payment of INR 4,25,00,000/- on 05/02/2024.",
        "",
        "CONCERNING THE INCIDENT OF 10/08/2024:",
        "On 10/08/2024, at approximately 11:30 AM, I accompanied MD Vikramaditya Singhania to Zenith's Okhla office.",
        "Accused Rajesh Malhotra was present in the boardroom along with two private security guards.",
        "When our MD demanded immediate access to the GitHub enterprise escrow keys, Rajesh Malhotra shouted at us.",
        "However, contrary to what was later written in the complaint, there was NO physical violence or assault.",
        "Rajesh Malhotra merely slammed the desk, hurled verbal abuses, and asked us to resolve the dispute in arbitration.",
        "Neither I nor Mr. Singhania suffered any bodily blows or physical injury whatsoever during this meeting.",
        "We left the Okhla premises peacefully at 12:15 PM and drove back to our Gurugram office.",
        "",
        "CONCERNING PRE-DISBURSEMENT DUE DILIGENCE:",
        "I state that our technical team led by Mr. Singhania had already inspected the beta software build in January 2024.",
        "The software architecture was working properly in the staging environment before any funds were released.",
        "The dispute arose primarily because Zenith demanded an additional INR 1.5 Crores for cloud GPU server costs.",
        "Statement recorded verbatim without fear, favor, or coercion.",
        "Sd/- Ramesh Gupta (Witness / CFO)."
    ]
    build_raw_pdf(pw1_lines, OUTPUT_DIR / "02_PW1_Statement_Section_161_CrPC.pdf")

    # 3. Medico-Legal Certificate (MLC)
    mlc_lines = [
        "DR. RAM MANOHAR LOHIA HOSPITAL, NEW DELHI - DEPARTMENT OF CASUALTY & FORENSIC MEDICINE",
        "MEDICO-LEGAL CERTIFICATE (MLC NO. 8841/2024)",
        "DATE & TIME OF EXAMINATION: 11/08/2024 at 09:45 PM IST",
        "--------------------------------------------------------------------------------",
        "PATIENT PARTICULARS:",
        "Name: Vikramaditya Singhania | Age: 49 Years | Gender: Male",
        "Brought By: Self, accompanied by advocate.",
        "Alleged History: Alleged physical assault by known business associates at Okhla Ph-III on 10/08/2024 at 11:30 AM.",
        "--------------------------------------------------------------------------------",
        "CLINICAL EXAMINATION FINDINGS:",
        "1. General Condition: Patient conscious, oriented in time, space and person. Pulse 78/min, BP 124/82 mmHg.",
        "2. External Physical Injuries Noted:",
        "   - Single superficial linear abrasion of 1.2 cm x 0.2 cm over dorsal aspect of left distal forearm.",
        "   - Color: Reddish crusting consistent with healing superficial contact. No active oozing.",
        "   - No contusions, hematoma, swelling, laceration, or incised wound detected anywhere on body.",
        "   - Skull, spine, ribs, thorax, abdomen, and limbs clinically intact and non-tender.",
        "3. Radiology / X-Ray Findings (Left Upper Extremity):",
        "   - Left forearm AP & Lateral View: No fracture, dislocation, or bony abnormality detected.",
        "--------------------------------------------------------------------------------",
        "FORENSIC OPINION & CLASSIFICATION:",
        "Nature of Injury: SIMPLE IN NATURE, caused by blunt/frictional contact with rough surface.",
        "Duration of Injury: Approximately 24 to 36 hours prior to examination.",
        "No evidence of grievous hurt, bone trauma, or dangerous weapon.",
        "Patient discharged immediately after antiseptic dressing. Hospitalization NOT required.",
        "",
        "EVIDENTIARY DEFICIENCIES NOTED:",
        "Note: This is a printed electronic record generated from hospital HIS terminal.",
        "No Certificate under Section 65B of Indian Evidence Act / Section 63 Bharatiya Sakshya Adhiniyam attached.",
        "Sd/- Dr. Anurag Batra, Casualty Medical Officer (CMO), RML Hospital, New Delhi."
    ]
    build_raw_pdf(mlc_lines, OUTPUT_DIR / "03_MLC_Medical_Report_RML_Hospital.pdf")

    # 4. Master Escrow & Software License Agreement
    contract_lines = [
        "MASTER SOFTWARE DEPLOYMENT AND ESCROW AGREEMENT",
        "EXECUTED AT NEW DELHI ON THIS 15TH DAY OF JANUARY, 2024",
        "BY AND BETWEEN: Apex FinTech Innovations Ltd. ('Customer') AND Zenith Cloud Technologies Pvt. Ltd. ('Vendor')",
        "--------------------------------------------------------------------------------",
        "RECITALS & OPERATIVE COVENANTS:",
        "WHEREAS Vendor possesses algorithmic software for automated core loan disbursements and settlements;",
        "AND WHEREAS Customer desires to license said software and engage Vendor for turnkey deployment;",
        "NOW THEREFORE THE PARTIES AGREE AS FOLLOWS:",
        "",
        "CLAUSE 2: CONTRACTUAL CONSIDERATION & PAYMENT MILESTONES:",
        "Total Contract Price: INR 8,50,00,000/- (Eight Crores Fifty Lakhs) plus applicable GST.",
        "Milestone 1: 50% (INR 4,25,00,000/-) payable upon execution and delivery of Source Code Escrow Confirmation.",
        "Milestone 2: 30% (INR 2,55,00,000/-) payable upon User Acceptance Testing (UAT) sign-off.",
        "Milestone 3: 20% (INR 1,70,00,000/-) payable upon 90 days of commercial live production.",
        "",
        "CLAUSE 9: ESCROW DEPOSIT AND TECHNICAL SPECIFICATIONS:",
        "Vendor covenants to deposit source code and encryption keys into escrow with CertiGuard Labs or any mutually",
        "approved escrow custodian. In the event of dispute over vendor capabilities, audit rights shall be exercised.",
        "",
        "CLAUSE 18: GOVERNING LAW AND EXCLUSIVE DISPUTE RESOLUTION (ARBITRATION):",
        "18.1 This Agreement shall be governed by and construed in accordance with the substantive laws of India.",
        "18.2 All disputes, controversies, or claims arising out of or in connection with this Agreement, including any",
        "question regarding its existence, validity, breach, or termination, shall be referred to and finally resolved",
        "by Arbitration administered by the Delhi International Arbitration Centre (DIAC) in accordance with DIAC Rules.",
        "18.3 The seat and venue of arbitration shall be New Delhi. The arbitral tribunal shall consist of a Sole Arbitrator.",
        "18.4 The parties expressly agree that breach of delivery milestones shall constitute a purely civil commercial",
        "breach remediable exclusively through liquidated damages capped at 15% of contract value or specific performance.",
        "",
        "IN WITNESS WHEREOF, the authorized signatories have executed this Agreement on 15/01/2024.",
        "Sd/- Vikramaditya Singhania (Apex FinTech) | Sd/- Rajesh Malhotra (Zenith Cloud)"
    ]
    build_raw_pdf(contract_lines, OUTPUT_DIR / "04_Master_Escrow_Agreement_Dated_15012024.pdf")

    print("\nAll 4 authentic Indian legal PDF exhibits generated successfully in:")
    print(OUTPUT_DIR.resolve())


if __name__ == "__main__":
    generate_all_case_documents()
