"""
Script to generate a comprehensive suite of dummy case files in the root folder 'dummy_case_files'.
These files represent an authentic Indian legal matter designed for testing the ALAS Case Files module:
- Document Classification (FIR, 161 CrPC Statement, MLC Report, Commercial Contract, Panchnama, Electronic Image)
- Chronological Timeline Extraction
- Cross-Document Witness Contradiction Analysis
- Penal & Statutory Ingredient Auditing (Sec 420, 406, 468, 471 IPC vs 318, 316 BNS)
- Procedural Defect & Missing Evidence Auditing (Lack of Sec 65B Certificate, Lack of Independent Panchas)
- Pre-trial Legal Precedent Research (Indian Kanoon)
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pypdf

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "dummy_case_files"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_raw_pdf(lines: list[str], output_path: Path):
    """
    Build a standard compliant PDF 1.4 document in pure Python.
    """
    lines_per_page = 40
    pages_lines = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
    if not pages_lines:
        pages_lines = [[""]]

    num_pages = len(pages_lines)
    
    font_obj_id = 3 + 2 * num_pages
    page_obj_ids = [3 + i for i in range(num_pages)]
    content_obj_ids = [3 + num_pages + i for i in range(num_pages)]
    
    objects = {}
    
    # 1: Catalog
    objects[1] = f"<< /Type /Catalog /Pages 2 0 R >>\n".encode("latin1")
    
    # 2: Pages
    kids_str = " ".join([f"{pid} 0 R" for pid in page_obj_ids])
    objects[2] = f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>\n".encode("latin1")
    
    # Font
    objects[font_obj_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
    
    # Pages & Content streams
    for idx, page_lines in enumerate(pages_lines):
        pid = page_obj_ids[idx]
        cid = content_obj_ids[idx]
        
        objects[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {cid} 0 R /Resources << /Font << /F1 {font_obj_id} 0 R >> >> >>\n"
        ).encode("latin1")
        
        stream = "BT /F1 9 Tf 40 750 Td 14 TL "
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
        
    print(f"Generated {output_path.name} ({len(body)} bytes, {num_pages} pages)")


def generate_fir_document():
    lines = [
        "FIRST INFORMATION REPORT (Under Section 154 Cr.P.C. / Section 173 BNSS, 2023)",
        "POLICE STATION: Economic Offences Wing (EOW), Mandir Marg, New Delhi",
        "DISTRICT: New Delhi | YEAR: 2024 | FIR NO: 0412/2024 | DATE & TIME: 14/08/2024 at 11:30 AM",
        "--------------------------------------------------------------------------------",
        "1. ACTS & STATUTORY SECTIONS CITED:",
        "   (a) Section 420 Indian Penal Code / Sec 318 BNS (Cheating & Dishonestly Inducing Delivery)",
        "   (b) Section 406 Indian Penal Code / Sec 316 BNS (Criminal Breach of Trust)",
        "   (c) Section 468 & 471 Indian Penal Code / Sec 336 & 340 BNS (Forgery for Cheating & Using Forged Document)",
        "   (d) Section 323 & 506 Indian Penal Code / Sec 115 & 351 BNS (Voluntarily Causing Hurt & Intimidation)",
        "   (e) Section 120-B Indian Penal Code / Sec 61 BNS (Criminal Conspiracy)",
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
        "physically assaulted Complainant's officers, caused severe bodily injuries, threatened criminal intimidation,",
        "and bolted the office doors to prevent escape.",
        "",
        "5. PRIMA FACIE FINDINGS OF INVESTIGATING OFFICER:",
        "The accused persons dishonestly induced the complainant to part with INR 4,25,00,000/- using forged credentials.",
        "Ingredients of cheating under Section 420 IPC and criminal breach of trust under Section 406 IPC are attracted.",
        "Investigation endorsed to SI Devendra Chawla, EOW Mandir Marg.",
        "Sd/- Inspector Devendra Chawla, Investigating Officer (EOW Delhi Police)."
    ]
    build_raw_pdf(lines, OUTPUT_DIR / "01_FIR_No_0412_2024_Mandir_Marg_PS.pdf")


def generate_pw1_statement():
    lines = [
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
        "CONCERNING THE INCIDENT OF 10/08/2024 (CROSS-EXAMINATION / CONTRADICTION POINT):",
        "On 10/08/2024, at approximately 11:30 AM, I accompanied MD Vikramaditya Singhania to Zenith's Okhla office.",
        "Accused Rajesh Malhotra was present in the boardroom along with two private security guards.",
        "When our MD demanded immediate access to the GitHub enterprise escrow keys, Rajesh Malhotra shouted at us.",
        "However, contrary to what was later stated in the FIR, there was NO physical violence or assault whatsoever.",
        "Rajesh Malhotra merely slammed the desk, hurled verbal abuses, and asked us to resolve the dispute in arbitration.",
        "Neither I nor Mr. Singhania suffered any bodily blows, fractures, or physical injury during this entire meeting.",
        "We left the Okhla premises peacefully at 12:15 PM and drove back to our Gurugram corporate headquarters.",
        "",
        "CONCERNING PRE-DISBURSEMENT DUE DILIGENCE & SOFTWARE INTEGRATION:",
        "I state that our technical team led by Mr. Singhania had already inspected the beta software build in January 2024.",
        "The software architecture was working properly in the staging environment before any funds were released.",
        "The dispute arose primarily because Zenith demanded an additional INR 1.5 Crores for cloud GPU server costs.",
        "Statement recorded verbatim without fear, favor, or coercion.",
        "Sd/- Ramesh Gupta (Witness / CFO)."
    ]
    build_raw_pdf(lines, OUTPUT_DIR / "02_PW1_Statement_Ramesh_Gupta_CFO_Sec161CrPC.pdf")


def generate_pw2_statement():
    lines = [
        "STATEMENT OF WITNESS UNDER SECTION 161 Cr.P.C. / SECTION 180 BNSS, 2023",
        "POLICE STATION: EOW, Mandir Marg, New Delhi | FIR NO: 0412/2024",
        "DATE OF EXAMINATION: 22/08/2024 | INVESTIGATING OFFICER: SI Devendra Chawla",
        "--------------------------------------------------------------------------------",
        "WITNESS IDENTIFICATION:",
        "Name: Sameer Verma, S/o Sh. V. K. Verma, Age: 39 Years",
        "Designation: Chief Technology Officer, Zenith Cloud Technologies Pvt. Ltd., New Delhi.",
        "--------------------------------------------------------------------------------",
        "WITNESS TESTIMONY & TECHNICAL DEFENCE:",
        "I am the CTO of Zenith Cloud Technologies Pvt. Ltd. and oversaw software architecture.",
        "I categorically deny any conspiracy, fraudulent misrepresentation, or cheating.",
        "Between January 2024 and June 2024, our 18-member engineering team built over 85,000 lines of modular",
        "Go and Python microservices for Apex FinTech's algorithmic clearing engine.",
        "The staging code was deployed on AWS Singapore instances with full CI/CD access provided to Apex engineers.",
        "",
        "REGARDING THE THIRD-PARTY ESCROW DEPOSIT:",
        "CertiGuard Labs was an independent technical compliance audit firm recommended by our international partners.",
        "We submitted the complete SHA-256 cryptographic hash of the source code repository to CertiGuard on 02/02/2024.",
        "The escrow confirmation receipt was issued legitimately after cryptographic verification.",
        "We never suppressed any source code; in fact, on 08/08/2024, we sent a formal email offering full repository transfer",
        "subject to Apex settling the outstanding AWS infrastructure hosting invoice of INR 68,50,000/-.",
        "",
        "REGARDING THE EVENTS OF 10/08/2024:",
        "On 10/08/2024 at 11:30 AM, Mr. Singhania and Mr. Gupta arrived unannounced and demanded instant master root keys.",
        "Mr. Malhotra explained that root keys could only be delivered upon signing the UAT handover and indemnity waiver.",
        "Mr. Singhania became infuriated, swept items off the conference table, and accidentally grazed his wrist against",
        "the sharp aluminium border of an open presentation easel.",
        "No employee of Zenith touched Mr. Singhania. CCTV footage of the boardroom foyer confirms this fact.",
        "The dispute is strictly a commercial contractual dispute governed by the DIAC arbitration clause in our agreement.",
        "Sd/- Sameer Verma (Witness / CTO)."
    ]
    build_raw_pdf(lines, OUTPUT_DIR / "03_PW2_Statement_Sameer_Verma_CTO_Sec161CrPC.pdf")


def generate_mlc_document():
    lines = [
        "DR. RAM MANOHAR LOHIA HOSPITAL, NEW DELHI - DEPARTMENT OF CASUALTY & FORENSIC MEDICINE",
        "MEDICO-LEGAL CERTIFICATE (MLC NO. 8841/2024)",
        "DATE & TIME OF EXAMINATION: 11/08/2024 at 09:45 PM IST (34 Hours after alleged incident)",
        "--------------------------------------------------------------------------------",
        "PATIENT PARTICULARS:",
        "Name: Vikramaditya Singhania | Age: 49 Years | Gender: Male",
        "Brought By: Self, accompanied by legal counsel.",
        "Alleged History: Alleged physical assault and beating by business associates at Okhla Ph-III on 10/08/2024 at 11:30 AM.",
        "--------------------------------------------------------------------------------",
        "CLINICAL EXAMINATION FINDINGS:",
        "1. General Condition: Patient conscious, oriented in time, space and person. Pulse 78/min, BP 124/82 mmHg.",
        "2. External Physical Injuries Noted:",
        "   - Single superficial linear abrasion measuring 1.2 cm x 0.2 cm over dorsal aspect of left distal forearm.",
        "   - Color: Reddish crusting consistent with healing superficial frictional contact. No active bleeding or oozing.",
        "   - No contusions, hematoma, swelling, laceration, or incised wound detected anywhere on body.",
        "   - Skull, spine, ribs, thorax, abdomen, and limbs clinically intact, non-tender, with full range of motion.",
        "3. Radiology / X-Ray Findings (Left Upper Extremity):",
        "   - Left forearm AP & Lateral View: No fracture, dislocation, or bony abnormality detected.",
        "--------------------------------------------------------------------------------",
        "FORENSIC OPINION & CLASSIFICATION:",
        "Nature of Injury: SIMPLE IN NATURE, caused by blunt/frictional contact with rough surface.",
        "Duration of Injury: Approximately 24 to 36 hours prior to examination.",
        "No evidence of grievous hurt, bone trauma, internal hemorrhage, or dangerous weapons.",
        "Patient discharged immediately after antiseptic dressing. Hospitalization NOT required.",
        "",
        "EVIDENTIARY DEFICIENCIES & PROCEDURAL COMPLIANCE AUDIT:",
        "CRITICAL DEFECT: This document is an uncertified computer printout from hospital HIS terminal.",
        "No mandatory Electronic Evidence Certificate under Section 65B of Indian Evidence Act, 1872 or",
        "Section 63 of Bharatiya Sakshya Adhiniyam (BSA), 2023 is affixed or signed by the system administrator.",
        "Sd/- Dr. Anurag Batra, Casualty Medical Officer (CMO), RML Hospital, New Delhi."
    ]
    build_raw_pdf(lines, OUTPUT_DIR / "04_MLC_Medical_Report_Dr_Anurag_Batra_RML_Hospital.pdf")


def generate_contract_document():
    lines = [
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
        "Neither party shall initiate penal or criminal proceedings in respect of milestone delay or technical variances.",
        "",
        "IN WITNESS WHEREOF, the authorized signatories have executed this Agreement on 15/01/2024.",
        "Sd/- Vikramaditya Singhania (Apex FinTech) | Sd/- Rajesh Malhotra (Zenith Cloud)"
    ]
    build_raw_pdf(lines, OUTPUT_DIR / "05_Master_Software_Escrow_Agreement_Dated_15012024.pdf")


def generate_seizure_panchnama():
    lines = [
        "SEIZURE MEMO AND PANCHNAMA (Under Section 102 Cr.P.C. / Section 106 BNSS, 2023)",
        "POLICE STATION: EOW, Mandir Marg, New Delhi | FIR NO: 0412/2024",
        "DATE OF SEIZURE: 24/08/2024 | TIME: 03:30 PM to 06:15 PM IST",
        "LOCATION: Registered Office of Zenith Cloud Technologies Pvt. Ltd., Okhla Phase-III, New Delhi.",
        "INVESTIGATING OFFICER: SI Devendra Chawla, EOW Mandir Marg.",
        "--------------------------------------------------------------------------------",
        "PANCH WITNESSES RECORDED IN MEMO:",
        "1. Head Constable Satbir Singh, No. 892/EOW, Delhi Police (Police Official / Non-Independent).",
        "2. Constable Virender Kumar, No. 1104/EOW, Delhi Police (Police Official / Non-Independent).",
        "--------------------------------------------------------------------------------",
        "DESCRIPTION OF ARTICLES AND ELECTRONIC RECORDS SEIZED:",
        "Item 1: One Lenovo ThinkPad P1 Gen 6 Laptop (Serial No. LNV-88219-X) purportedly used by CTO Sameer Verma.",
        "Item 2: Hard disk partition clone containing Git repository backups and escrow correspondence files.",
        "Item 3: Bank account statements of Zenith Cloud Technologies Pvt. Ltd. (HDFC Bank Okhla Branch A/c 502000318921).",
        "Item 4: One paper binder containing duplicate carbon copy of Master Software Agreement dated 15/01/2024.",
        "",
        "SEIZURE PROCEDURE AND OBSERVATIONS:",
        "The electronic devices were seized from the open technical bay without using static-shielded anti-tamper forensic bags.",
        "Hash values (MD5 / SHA-256) of the seized storage drive were NOT generated at the time and spot of seizure.",
        "No independent civilian or public witnesses from the commercial industrial locality were joined in the Panchnama.",
        "Both memo witnesses are subordinate police officers attached to the same police station.",
        "",
        "PROCEDURAL COMPLIANCE DEFICIENCIES NOTED FOR DEFENCE BRIEF:",
        "1. Violation of Section 100(4) CrPC / Section 103 BNSS: Failure to join two independent and respectable inhabitants.",
        "2. Violation of Delhi High Court Forensic Guidelines: Failure to generate cryptographic SHA-256 hash at the seizure locus.",
        "3. Missing Section 65B Indian Evidence Act / Section 63 BSA Certificate for the seized electronic files.",
        "Sd/- SI Devendra Chawla (IO) | Sd/- HC Satbir Singh (Panch 1) | Sd/- Ct Virender (Panch 2)"
    ]
    build_raw_pdf(lines, OUTPUT_DIR / "06_Forensic_Audit_Report_and_Seizure_Panchnama.pdf")


def generate_chat_screenshot_image():
    """
    Generate an evidentiary WhatsApp chat screenshot image (PNG)
    between Rajesh Malhotra (Zenith) and Vikramaditya Singhania (Apex).
    """
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), color=(240, 242, 245))
    draw = ImageDraw.Draw(img)
    
    # WhatsApp Header (Dark Teal #075E54)
    draw.rectangle([0, 0, width, 100], fill=(7, 94, 84))
    
    # Header Text
    # We use default font since PIL default is always present
    draw.text((30, 25), "Vikramaditya Singhania (Apex FinTech MD)", fill=(255, 255, 255))
    draw.text((30, 55), "+91 98110 XXXXX - Online", fill=(200, 230, 220))
    draw.text((620, 40), "09/08/2024", fill=(255, 255, 255))
    
    # Chat Background subheader: Date Pill
    date_pill_x1, date_pill_y1, date_pill_x2, date_pill_y2 = 300, 120, 500, 155
    draw.rectangle([date_pill_x1, date_pill_y1, date_pill_x2, date_pill_y2], fill=(225, 230, 235))
    draw.text((345, 130), "9 AUGUST 2024", fill=(80, 90, 100))
    
    # Message 1 - Received (Complainant Singhania to Malhotra) - Left bubble (White)
    draw.rectangle([40, 180, 560, 270], fill=(255, 255, 255), outline=(220, 220, 220))
    draw.text((55, 195), "Rajesh, we reviewed the beta clearing engine in staging.", fill=(20, 20, 20))
    draw.text((55, 215), "Architecture looks solid, but we need the master escrow keys", fill=(20, 20, 20))
    draw.text((55, 235), "before board clearance next Tuesday.", fill=(20, 20, 20))
    draw.text((490, 248), "03:45 PM", fill=(130, 140, 150))
    
    # Message 2 - Sent (Accused Malhotra to Singhania) - Right bubble (#DCF8C6 Light Green)
    draw.rectangle([240, 290, 760, 395], fill=(220, 248, 198), outline=(190, 225, 175))
    draw.text((255, 305), "Hi Vikramaditya. Absolutely, the escrow deposit was completed", fill=(20, 20, 20))
    draw.text((255, 325), "with CertiGuard. Please clear the pending AWS cluster fee", fill=(20, 20, 20))
    draw.text((255, 345), "(INR 68.5L) so we can issue production keys.", fill=(20, 20, 20))
    draw.text((255, 365), "Let's meet tomorrow 10/08 at 11:30 AM at our Okhla office.", fill=(20, 20, 20))
    draw.text((690, 375), "04:12 PM \u2713\u2713", fill=(70, 140, 70))
    
    # Message 3 - Received (Singhania to Malhotra)
    draw.rectangle([40, 415, 600, 495], fill=(255, 255, 255), outline=(220, 220, 220))
    draw.text((55, 430), "Agreed. I will bring CFO Ramesh Gupta with me.", fill=(20, 20, 20))
    draw.text((55, 450), "We will review the escrow hash and reconcile the cloud invoice.", fill=(20, 20, 20))
    draw.text((55, 470), "See you tomorrow at 11:30 AM in Okhla.", fill=(20, 20, 20))
    draw.text((530, 473), "04:30 PM", fill=(130, 140, 150))
    
    # Message 4 - Sent (Malhotra to Singhania)
    draw.rectangle([340, 515, 760, 585], fill=(220, 248, 198), outline=(190, 225, 175))
    draw.text((355, 530), "Perfect. Sameer Verma (CTO) will also be present.", fill=(20, 20, 20))
    draw.text((355, 550), "Looking forward to closing Milestone-1 handover.", fill=(20, 20, 20))
    draw.text((690, 565), "04:45 PM \u2713\u2713", fill=(70, 140, 70))
    
    # Forensic Evidence Stamp Banner at bottom
    draw.rectangle([40, 640, 760, 940], fill=(245, 245, 240), outline=(180, 180, 180))
    draw.text((60, 660), "CENTRAL FORENSIC SCIENCE LABORATORY (CFSL) - DIGITAL EVIDENCE EXHIBIT", fill=(180, 30, 30))
    draw.text((60, 690), "Exhibit Mark: DEF-EX-07 | Case: FIR No. 0412/2024 PS Mandir Marg / EOW", fill=(30, 30, 30))
    draw.text((60, 720), "Extracted From: Apple iPhone 15 Pro (IMEI: 356891048291042) belonging to Accused", fill=(50, 50, 50))
    draw.text((60, 750), "Evidentiary Significance:", fill=(10, 10, 10))
    draw.text((60, 775), "1. Establishes cordial pre-meeting commercial dialogue on 09/08/2024.", fill=(50, 50, 50))
    draw.text((60, 800), "2. Complainant acknowledges software was inspected and functioning in staging.", fill=(50, 50, 50))
    draw.text((60, 825), "3. Proves meeting on 10/08/2024 was scheduled by mutual consent, refuting criminal trespass.", fill=(50, 50, 50))
    draw.text((60, 860), "DEFICIENCY: Forensic export lacks Section 65B Certificate under Indian Evidence Act.", fill=(180, 50, 0))
    draw.text((60, 895), "CFSL Hash: SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", fill=(100, 100, 100))
    
    img_path = OUTPUT_DIR / "07_Evidentiary_WhatsApp_Chat_Screenshot.png"
    img.save(img_path)
    print(f"Generated {img_path.name} ({img_path.stat().st_size} bytes)")


def generate_readme():
    content = """# Dummy Legal Case Files for ALAS Testing

This directory contains realistic, authentic Indian legal case files specifically constructed to test all capabilities of the **ALAS Case Files Intelligence Engine** (`/dashboard/cases`).

---

## 🏛️ Case Matter Overview
- **Matter Caption**: *State (NCT of Delhi) & Apex FinTech Innovations Ltd. vs. Zenith Cloud Technologies Pvt. Ltd. & Ors.*
- **FIR Number**: 0412/2024 (PS Mandir Marg / Economic Offences Wing, New Delhi)
- **Jurisdiction**: Hon'ble High Court of Delhi (Criminal Miscellaneous Main / Commercial Quashing under Section 482 CrPC / Section 528 BNSS)
- **Subject**: Alleged INR 4.25 Crore software escrow fraud vs. bona fide civil commercial milestone dispute with contractual arbitration clause.

---

## 📁 File Manifest & Targeted ALAS Intelligence Agents

| # | File Name | Document Type | Key Intelligence Triggers |
|---|---|---|---|
| 1 | `01_FIR_No_0412_2024_Mandir_Marg_PS.pdf` | Police FIR (Sec 154 CrPC / Sec 173 BNSS) | **Document Classifier**, **Chronological Timeline**, **Penal Charge Auditing** (Sec 420, 406, 468, 471, 120-B IPC; 318, 316 BNS). Alleges severe assault. |
| 2 | `02_PW1_Statement_Ramesh_Gupta_CFO_Sec161CrPC.pdf` | Witness Statement (Sec 161 CrPC / Sec 180 BNSS) | **Witness Contradiction Agent**: CFO Ramesh Gupta directly contradicts the FIR narrative—states that **no physical assault or violence occurred** on 10/08/2024, and confirms beta software worked properly. |
| 3 | `03_PW2_Statement_Sameer_Verma_CTO_Sec161CrPC.pdf` | Witness Statement (Sec 161 CrPC / Sec 180 BNSS) | **Issue / Charge Agent**: Demonstrates 85,000 lines of code written on AWS, negating fraudulent intent from inception (*Hridaya Ranjan Prasad Verma* doctrine). Explains the accidental wrist graze. |
| 4 | `04_MLC_Medical_Report_Dr_Anurag_Batra_RML_Hospital.pdf` | Medico-Legal Certificate (MLC) | **Contradiction & Missing Evidence Agent**: 34-hour delay in examination; classifies injury as "SIMPLE IN NATURE" (single 1.2cm scratch), debunking grievous assault claims. Flags **lack of Section 65B / 63 BSA certificate** on HIS printout. |
| 5 | `05_Master_Software_Escrow_Agreement_Dated_15012024.pdf` | Commercial Contract | **Contractual Analysis & Legal Research Agent**: Clause 18 contains a mandatory **DIAC Arbitration** clause and caps liquidated damages at 15%, establishing civil remedy bar to criminal prosecution. |
| 6 | `06_Forensic_Audit_Report_and_Seizure_Panchnama.pdf` | Seizure Memo & Panchnama | **Procedural Compliance Agent**: Detects major procedural flaws—no independent civilian panchas (only police officers), failure to generate SHA-256 hash at scene of seizure, violation of Sec 100(4) CrPC. |
| 7 | `07_Evidentiary_WhatsApp_Chat_Screenshot.png` | Digital Image Evidence | **Multimodal Pixtral OCR & Vision Agent**: Tests image OCR and visual analysis. Proves cordial scheduling of 10/08/2024 meeting and pre-disbursement beta testing. |

---

## 🚀 How to Upload & Test in ALAS UI

1. **Start ALAS** (Backend & Frontend):
   - Backend: `./start_backend.ps1` (or `uvicorn backend.main:app --reload --port 8000`)
   - Frontend: `cd frontend && pnpm run dev`
2. **Open the Case Files Dashboard**:
   - Navigate to: `http://localhost:3000/dashboard/cases`
3. **Create a Case File**:
   - Click **"Create New Case File"** (or "+ New Case").
   - Title: `State & Apex FinTech vs. Zenith Cloud Technologies (FIR 0412/2024)`
   - Description: `Alleged software escrow cheating under Sec 420/406 IPC vs commercial milestone dispute with DIAC arbitration.`
4. **Upload the Files**:
   - In the Case Workspace, click **"Upload Documents"**.
   - Browse to this directory: `c:\\Users\\Prajwal\\code\\ALASv2\\dummy_case_files\\`
   - Select all 7 files (or upload them individually).
5. **Run AI Multi-Agent Intelligence**:
   - Click **"Run Comprehensive Analysis"**.
   - The LangGraph Orchestrator will execute:
     - Document Classifier
     - Timeline Agent (Chronological events from 15/01/2024 to 24/08/2024)
     - Witness Contradiction Agent (Highlighting FIR vs. CFO vs. MLC contradictions)
     - Penal Ingredient Auditor (IPC vs BNS statutory element analysis)
     - Procedural Compliance Auditor (Missing 65B certificates, improper panchnama)
     - Precedent Research (Searching *Indian Kanoon* for *Hridaya Ranjan Prasad Verma*, *Arnesh Kumar*, etc.)
6. **Interact with Pre-Trial Tools**:
   - **Case Q&A**: Ask *"Did any physical assault occur during the August 10 meeting?"* or *"What procedural defects exist in the seizure memo?"*
   - **Adversarial Courtroom Debate**: Run Prosecution vs. Defence debate to view judge verdict and legal strategy recommendations!
"""
    with open(OUTPUT_DIR / "README.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("Generated dummy_case_files/README.md")


if __name__ == "__main__":
    print(f"Generating dummy legal case files in: {OUTPUT_DIR}\n")
    generate_fir_document()
    generate_pw1_statement()
    generate_pw2_statement()
    generate_mlc_document()
    generate_contract_document()
    generate_seizure_panchnama()
    generate_chat_screenshot_image()
    generate_readme()
    print("\nAll dummy case files generated successfully!")
