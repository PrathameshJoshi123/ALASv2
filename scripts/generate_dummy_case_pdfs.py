"""
Generate authentic, high-fidelity Indian legal dummy case PDF files
for the Pre-Trial Adversarial Courtroom Debate System.

Case Matter:
Apex FinTech Innovations Ltd. vs. Zenith Cloud Technologies Pvt. Ltd. & Ors.
FIR No. 0412/2024 (EOW / Mandir Marg PS)
Hon'ble High Court of Delhi (Crl. Misc. Main under Sec 482 CrPC / Sec 528 BNSS)
"""

import os
from pathlib import Path
import pymupdf as fitz

TARGET_DIR = Path("backend/storage/dummy_cases/apex_vs_zenith")
TARGET_DIR.mkdir(parents=True, exist_ok=True)


def draw_header(page, court_or_dept: str, doc_title: str):
    rect = fitz.Rect(50, 40, page.rect.width - 50, page.rect.height - 40)
    # Border
    page.draw_rect(rect, color=(0.2, 0.2, 0.2), width=1)
    # Header box
    header_rect = fitz.Rect(50, 40, page.rect.width - 50, 95)
    page.draw_rect(header_rect, color=(0.2, 0.2, 0.2), fill=(0.95, 0.95, 0.95), width=1)
    
    page.insert_text((page.rect.width / 2 - len(court_or_dept) * 3.2, 60), court_or_dept, fontsize=11, fontname="helv", color=(0.1, 0.1, 0.1))
    page.insert_text((page.rect.width / 2 - len(doc_title) * 3.6, 80), doc_title, fontsize=12, fontname="helv", color=(0.05, 0.05, 0.05))


def render_multiline(page, text: str, start_x: float, start_y: float, max_width: float, font_size: float = 10, line_height: float = 14) -> float:
    y = start_y
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            y += line_height * 0.7
            continue
        words = paragraph.split(" ")
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            # rough estimate 0.5 * font_size per character
            if len(test_line) * (font_size * 0.52) > max_width and current_line:
                page.insert_text((start_x, y), " ".join(current_line), fontsize=font_size, fontname="helv")
                y += line_height
                current_line = [word]
            else:
                current_line.append(word)
        if current_line:
            page.insert_text((start_x, y), " ".join(current_line), fontsize=font_size, fontname="helv")
            y += line_height
    return y


def build_fir_pdf():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842) # A4
    draw_header(page, "GOVERNMENT OF NCT OF DELHI - DELHI POLICE (ECONOMIC OFFENCES WING)", "FIRST INFORMATION REPORT (Under Sec 173 BNSS, 2023 / Sec 154 CrPC, 1973)")
    
    content = (
        "1. DISTRICT: New Delhi | P.S.: Economic Offences Wing, Mandir Marg | YEAR: 2024\n"
        "   FIR NO.: 0412/2024 | DATE & TIME: 14/08/2024 at 11:30 AM IST\n\n"
        "2. STATUTORY SECTIONS CITED:\n"
        "   (a) Section 406 IPC / Section 316 BNS, 2023 (Criminal Breach of Trust)\n"
        "   (b) Section 420 IPC / Section 318 BNS, 2023 (Cheating & Dishonestly Inducing Delivery)\n"
        "   (c) Section 468 & 471 IPC / Section 336 & 340 BNS, 2023 (Forgery of Security Audit)\n"
        "   (d) Section 120-B IPC / Section 61 BNS, 2023 (Criminal Conspiracy)\n\n"
        "3. DETAILS OF COMPLAINANT:\n"
        "   Mr. Vikramaditya Singhania, Managing Director, Apex FinTech Innovations Ltd.,\n"
        "   Registered Office: Cyber City, Tower B, Level 14, Gurugram, NCR.\n\n"
        "4. DETAILS OF ACCUSED PERSONS:\n"
        "   Accused No. 1: Rajesh Malhotra, Managing Director, Zenith Cloud Technologies Pvt. Ltd.\n"
        "   Accused No. 2: Sameer Verma, Chief Technical Officer, Zenith Cloud Technologies Pvt. Ltd.\n"
        "   Accused No. 3: M/s Zenith Cloud Technologies Pvt. Ltd., Okhla Industrial Area Ph-III, New Delhi.\n\n"
        "5. COMPLAINT NARRATIVE & SUBSTANTIVE FACTS:\n"
        "The complainant company entered into a Master Software Deployment and Escrow Agreement with the "
        "accused on 15/01/2024 for implementing an automated core lending clearing infrastructure. The total "
        "consideration was INR 8,50,00,000/-. Under Clause 3, the complainant disbursed Milestone Tranche-1 of "
        "INR 4,25,00,000/- into an agreed project escrow account upon the accused furnishing a CertiGuard Labs "
        "ISO/IEC 27001 Security Audit and Escrow Deposit Confirmation dated 04/02/2024.\n\n"
        "Subsequent forensic audit by complainant revealed that CertiGuard Labs was a shell dummy entity registered "
        "by the brother-in-law of Accused No. 1. No code was ever deposited into independent third-party escrow. "
        "Within 48 hours of credit, INR 4,10,00,000/- was systematically round-tripped into personal demat and "
        "real-estate shell entities (Malhotra Ventures LLP). When milestone delivery was demanded in July 2024, "
        "the accused switched off servers, cited fictitious semiconductor supply chain embargoes, and threatened "
        "the complainant with arbitration delays.\n\n"
        "6. PRIMA FACIE OPINION OF INVESTIGATING OFFICER:\n"
        "Accused persons knowingly fabricated verification certificates and induced disbursement with fraudulent "
        "intent right from inception. Prima facie offenses under Sections 420, 406, 468, 471, 120-B IPC substantiated. "
        "Investigation taken up.\n\n"
        "Sd/- Inspector Devendra Chawla, Investigating Officer, EOW, New Delhi."
    )
    render_multiline(page, content, 70, 115, 455, font_size=9.5, line_height=13.5)
    
    out_path = TARGET_DIR / "01_FIRST_INFORMATION_REPORT_FIR_0412_2024.pdf"
    doc.save(str(out_path))
    doc.close()
    print(f"Generated: {out_path}")


def build_agreement_pdf():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    draw_header(page, "COMMERCIAL CONTRACT & DEPLOYMENT COVENANTS", "MASTER SOFTWARE ESCROW & LICENSING AGREEMENT")
    
    content = (
        "THIS MASTER AGREEMENT is entered into on this 15th Day of January 2024 at New Delhi by and between:\n\n"
        "1. APEX FINTECH INNOVATIONS LTD. ('Customer / Licensee')\n"
        "2. ZENITH CLOUD TECHNOLOGIES PVT. LTD. ('Vendor / Developer')\n\n"
        "OPERATIVE CLAUSES & RECITALS:\n\n"
        "CLAUSE 2. SCOPE & DELIVERABLES:\n"
        "Vendor covenants that it is the sole proprietary owner of the 'Zenith Ledger Engine v4.0' and possesses "
        "unencumbered right to license the clearing engine for institutional banking integrations.\n\n"
        "CLAUSE 3. CONSIDERATION & ESCROW MILESTONES:\n"
        "3.1 Total project consideration is agreed at INR 8,50,00,000/- (Indian Rupees Eight Crores Fifty Lakhs).\n"
        "3.2 Tranche 1 (50% - INR 4,25,00,000/-) payable upon execution and submission of certified Third-Party "
        "Security & Escrow Deposit Verification from an accredited certifier.\n"
        "3.3 Escrow funds shall remain dedicated exclusively to core infrastructure cloud hosting and developer "
        "payroll until Final User Acceptance Testing (UAT) signoff.\n\n"
        "CLAUSE 7. REPRESENTATIONS & WARRANTIES ON FRAUD:\n"
        "Vendor represents and warrants that all technical certifications, benchmark audits, and escrow custody "
        "receipts submitted to Customer represent authentic, verifiable technical artifacts free of misrepresentation.\n\n"
        "CLAUSE 14. GOVERNING LAW & MANDATORY ARBITRATION:\n"
        "14.1 This Agreement shall be governed by and construed in accordance with the laws of India.\n"
        "14.2 All disputes, claims, or controversies arising out of or in connection with this Agreement, including "
        "allegations of breach or non-performance, shall be exclusively referred to and finally resolved by "
        "Arbitration administered by the Delhi International Arbitration Centre (DIAC). The seat of arbitration "
        "shall be New Delhi. The courts of New Delhi shall have supervisory jurisdiction subject to arbitration.\n\n"
        "IN WITNESS WHEREOF the Authorized Signatories have executed this Agreement.\n"
        "For Apex FinTech Innovations Ltd.: [Sd/- V. Singhania, MD]\n"
        "For Zenith Cloud Technologies Pvt. Ltd.: [Sd/- Rajesh Malhotra, MD]"
    )
    render_multiline(page, content, 70, 115, 455, font_size=9.5, line_height=13.5)
    
    out_path = TARGET_DIR / "02_MASTER_ESCROW_AND_SOFTWARE_LICENSE_AGREEMENT.pdf"
    doc.save(str(out_path))
    doc.close()
    print(f"Generated: {out_path}")


def build_evidence_transcripts_pdf():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    draw_header(page, "ANNEXURE OF DIGITAL EXHIBITS & EVIDENTIARY RECORD", "EXHIBIT P-1 TO P-3: BANK ESCROW STATEMENTS & WHATSAPP TRANSCRIPTS")
    
    content = (
        "EXHIBIT P-1: HDFC ESCROW ACCOUNT AUDIT DEBITS (Account No. 50200049182012):\n"
        "- 18/01/2024: Credit of INR 4,25,00,000/- from Apex FinTech (UTR: HDFCR52024011800291).\n"
        "- 19/01/2024: Debit INR 2,00,00,000/- to 'Malhotra Ventures LLP' (Narration: Loan Repayment).\n"
        "- 20/01/2024: Debit INR 2,10,00,000/- to 'Zenith Holdings Dubai FZE' (Narration: Overseas Consultancy).\n"
        "- Residual Balance on 21/01/2024: INR 15,00,000/- only.\n\n"
        "EXHIBIT P-2: DIGITAL WHATSAPP TRANSCRIPT AUDIT (Extracted from Complainant's Corporate Mobile):\n"
        "Participants: Rajesh Malhotra (MD Zenith) & Vikramaditya Singhania (MD Apex)\n\n"
        "[16/01/2024, 14:15] Rajesh Malhotra: 'Vikram, our ISO audit from CertiGuard is cleared. Escrow depository "
        "is active. Release the 4.25 Cr so we deploy the staging servers tonight.'\n"
        "[16/01/2024, 14:32] V. Singhania: 'Approved and wired. Expecting UAT sandbox by March 15.'\n"
        "[12/07/2024, 11:02] V. Singhania: 'Rajesh, staging servers are dead for 3 weeks. Your CTO is unreachable. "
        "CertiGuard denies ever issuing certificate #CG-8829. Explain immediately.'\n"
        "[12/07/2024, 16:40] Rajesh Malhotra: 'Do what you want. Contract has Clause 14 DIAC arbitration. If you go "
        "to court, it will take 5 years. Better settle for 50 Lakhs credit note.'\n\n"
        "CRITICAL EVIDENTIARY DEFICIENCY & BENCH FLAG:\n"
        "NOTE: These printouts of WhatsApp communications and bank statement screenshots were produced by complainant "
        "without the mandatory Certificate under Section 65B(4) of Indian Evidence Act, 1872 / Section 63(4) of "
        "Bharatiya Sakshya Adhiniyam, 2023 signed by the system administrator or device custodian. Primary mobile device "
        "not submitted for hash-sum verification."
    )
    render_multiline(page, content, 70, 115, 455, font_size=9.5, line_height=13.5)
    
    out_path = TARGET_DIR / "03_EVIDENTIARY_RECORD_BANK_ADVICES_AND_ELECTRONIC_TRANSCRIPTS.pdf"
    doc.save(str(out_path))
    doc.close()
    print(f"Generated: {out_path}")


def build_legal_demand_and_reply_pdf():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    draw_header(page, "PRE-LITIGATION LEGAL CORRESPONDENCE", "FORMAL DEMAND NOTICE & RESPONDENT COUNSEL REBUTTAL")
    
    content = (
        "PART A: LEGAL DEMAND NOTICE DATED 15/07/2024\n"
        "Issued by: Singhania & Partners LLP, Advocates for Apex FinTech Innovations Ltd.\n"
        "To: Zenith Cloud Technologies Pvt. Ltd. & Rajesh Malhotra\n\n"
        "\"You the addressees knowingly made false, dishonest representations regarding code readiness and escrow "
        "depository to induce our client into transferring INR 4.25 Crores. You diverted these funds within 48 hours. "
        "We hereby demand unconditional refund of INR 4,25,00,000/- with 18% p.a. interest within 15 days, failing "
        "which criminal proceedings under Section 420/406/120-B IPC will be instituted without further notice.\"\n\n"
        "PART B: FORMAL REPLY NOTICE DATED 28/07/2024\n"
        "Issued by: Malhotra Chambers of Law, Advocates for Zenith Cloud Technologies Pvt. Ltd.\n\n"
        "\"1. The contents of your notice are baseless, defamatory, and an impermissible attempt to criminalize a bona "
        "fide commercial transaction.\n"
        "2. Our clients actively performed under the Master Agreement for over 5 months. The cloud latency and deliverable "
        "delays were entirely caused by third-party global AWS outage and semiconductor server component embargoes, "
        "constituting Force Majeure under Section 56 of Indian Contract Act, 1872.\n"
        "3. Mere subsequent inability to fulfill contractual milestones does not constitute cheating under Section 415/420 IPC. "
        "As authoritatively held by the Supreme Court in Dalip Kaur v. Jagnar Singh (2009) 14 SCC 696 and Indian Oil Corp v. "
        "NEPC India (2006) 6 SCC 736, criminal proceedings cannot be used as a coercive recovery weapon where a contract "
        "contains an arbitration clause (Clause 14 DIAC). Any criminal complaint will be resisted with quashing under Sec 482 CrPC.\""
    )
    render_multiline(page, content, 70, 115, 455, font_size=9.5, line_height=13.5)
    
    out_path = TARGET_DIR / "04_LEGAL_DEMAND_NOTICE_AND_REPLY_MEMORANDUM.pdf"
    doc.save(str(out_path))
    doc.close()
    print(f"Generated: {out_path}")


def build_quashing_petition_pdf():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    draw_header(page, "IN THE HIGH COURT OF DELHI AT NEW DELHI", "PETITION UNDER SECTION 482 CrPC / SECTION 528 BNSS (QUASHING)")
    
    content = (
        "CRIMINAL MISCELLANEOUS (MAIN) NO. 2891 OF 2024\n\n"
        "IN THE MATTER OF:\n"
        "1. Rajesh Malhotra, Managing Director\n"
        "2. Sameer Verma, CTO\n"
        "3. Zenith Cloud Technologies Pvt. Ltd. ... PETITIONERS\n"
        "VERSUS\n"
        "1. State (Govt. of NCT of Delhi)\n"
        "2. Apex FinTech Innovations Ltd. ... RESPONDENTS\n\n"
        "MEMORANDUM OF GROUNDS FOR QUASHING FIR NO. 0412/2024:\n\n"
        "A. DISPUTE IS PURELY COMMERCIAL WITH ARBITRATION SEAT:\n"
        "The disputes between the parties arise strictly from contractual covenants of the Master Agreement dated 15/01/2024. "
        "Clause 14 explicitly designates DIAC arbitration as the sole dispute mechanism. The complainant is abusing criminal "
        "machinery to avoid paying arbitration filing fees and bypass the commercial court.\n\n"
        "B. ABSENCE OF FRAUDULENT INTENT AT INCEPTION:\n"
        "Under the landmark rulings in Dalip Kaur v. Jagnar Singh (2009) 14 SCC 696 and Prof. R.K. Vijayasarathy v. Sudha Seetharam "
        "(2019) 16 SCC 739, an offense of cheating requires fraudulent intention right at inception. The petitioners actively "
        "delivered staging architecture for five months. Subsequent breach due to vendor cost spikes is a civil wrong, not criminal.\n\n"
        "C. INADMISSIBILITY OF ELECTRONIC EVIDENCE:\n"
        "The complainant's entire FIR hinges on uncertified WhatsApp printouts and third-party bank slips without a Section 65B(4) "
        "Evidence Act certificate. Under Arjun Panditrao Khotkar v. Kailash Kushanrao Gorantyal (2020) 7 SCC 1, electronic evidence "
        "without contemporaneous certification is inadmissible in law and cannot form the basis of cognizance.\n\n"
        "PRAYER: Quash FIR No. 0412/2024 and all proceedings emanating therefrom."
    )
    render_multiline(page, content, 70, 115, 455, font_size=9.5, line_height=13.5)
    
    out_path = TARGET_DIR / "05_SECTION_482_CRPC_QUASHING_PETITION.pdf"
    doc.save(str(out_path))
    doc.close()
    print(f"Generated: {out_path}")


def main():
    print("Generating comprehensive legal case files in PDF format...")
    build_fir_pdf()
    build_agreement_pdf()
    build_evidence_transcripts_pdf()
    build_legal_demand_and_reply_pdf()
    build_quashing_petition_pdf()
    print("All 5 case documents created successfully in backend/storage/dummy_cases/apex_vs_zenith/")


if __name__ == "__main__":
    main()
