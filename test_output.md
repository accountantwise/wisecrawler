# WiseCrawler — Test Output
**Date:** 2026-04-08  
**Target:** https://identiom.com  
**Provider:** OpenRouter (`openai/gpt-4o-mini`)

---

## Test 1: POST /v1/scrape/summarize

**Request:**
```json
{"url": "https://identiom.com"}
```

**Response:**

### Welcome to Identiom

Identiom specializes in delivering tailored Information Technology services for Professional Services, Asset Management firms, and High-Net-Worth Individuals. Our mission is to alleviate the concerns associated with managing your IT systems while significantly enhancing your **cybersecurity** capabilities.

---

## Cyber Security

Navigating the complexities of effective cybersecurity can be daunting. The continuous influx of devices, evolving security threats, and the sophistication of cybercriminals complicate matters. At Identiom, we utilize cutting-edge cybersecurity endpoint protection, detection, and response technologies. Safeguarding your organization against digital threats is our top priority, and we are committed to maximizing your security measures.

---

## Advanced Technology Management

Identiom offers a comprehensive technology consultancy and management service. We invest time in understanding your business and IT systems, allowing us to tailor our services to meet your specific needs effectively. By fostering strong relationships with you and your team, we ensure a high level of protection and commitment throughout our collaboration.

---

## Operational Management

As your dedicated advocate, Identiom provides practical guidance to help you make informed decisions that yield long-term benefits. From system design to ongoing monitoring and management, we prioritize attention to detail in every aspect of our service. Our hands-on approach ensures we deliver the best day-to-day IT support with a proven track record.

---

## Wealth of Experience

With over 20 years in the industry, Richard McDonald, the founder of Identiom, has established long-lasting and trusting relationships with more than 80 hedge fund clients. Our extensive experience and proven results mean you can trust us to manage your interests with discretion and integrity.

---

## Intimate & Personal Relationship

At Identiom, we believe in maintaining an intimate client relationship by accepting only a limited number of clients. This ensures that our clients receive the personalized support they need. We prioritize building long-term trusted partnerships, prompting some clients to view us as friends. Our dedicated team is always available to support you, your family, and your business when you need it most.

---

## The 4 C's

Identiom operates on the principles of Commitment, Clarity, Connection, and Confidentiality. We strive to offer transparent and concise guidance, ensuring you receive the highest level of service tailored to your needs.

---

## Test 2: POST /v1/crawl/analyze

**Crawl:** 2 pages crawled from https://identiom.com (maxDepth: 2, limit: 10)

**Prompt:** *What does this company do? Who are their target clients and what makes them different from competitors?*

**Response (`pages_analyzed: 2, was_truncated: false`):**

Identiom is a firm that specializes in providing Information Technology (IT) services tailored specifically for Professional Services, Asset Management firms, and High-Net-Worth Individuals (HNWIs). Their offerings primarily focus on comprehensive cyber security, advanced technology management, and operational management for their clients.

### Target Clients
1. **Professional Services** — Firms that require bespoke IT solutions and reliable cyber security.
2. **Asset Management Firms** — Companies involved in managing assets and investments, for whom data protection is crucial.
3. **High-Net-Worth Individuals** — Wealthy individuals who need personalized IT services, cybersecurity solutions, and overall management of their IT systems.

### Unique Selling Points
1. **Personalized Service** — Identiom limits its client base to ensure that every client receives an intimate and personal relationship with dedicated personnel. This approach fosters trust and provides tailored services specific to the client's needs.
2. **Expertise in Cybersecurity** — With a focus on high-stakes environments, Identiom emphasizes advanced cybersecurity practices, including Zero Trust Network Design, vulnerability management, and dark web monitoring.
3. **Long-Term Relationships** — The company aims to build long-lasting relationships with clients, reinforced by the founder's extensive experience with hedge funds and HNWIs.
4. **Commitment to the 4 C's** — Commitment, Clarity, Connection, and Confidentiality ensure clients receive clear guidance and the highest level of service possible.
5. **Proactive Monitoring** — Robust monitoring services including employee activity monitoring and dark web alerts keep clients informed about potential security threats.

Overall, Identiom differentiates itself through its focus on personalized service, significant expertise in cybersecurity, and commitment to forging deep, trusting relationships with its clients.

---

## Test 3: POST /v1/crawl/analyze (used as summarize)

**Crawl:** reused crawl job from Test 2 (2 pages, https://identiom.com)

**Prompt:** *Summarize the following web page content concisely. Include the main topic, key points, and any important details.*

**Response (`pages_analyzed: 2, was_truncated: false`):**

Identiom is a technology services provider specializing in cybersecurity and IT management for Professional Services, Asset Management firms, and High-Net-Worth Individuals (HNWIs). The company aims to alleviate concerns surrounding IT systems while enhancing cybersecurity measures.

**Main Topics:**

1. **Cybersecurity** — Importance of robust cybersecurity due to evolving threats. Offers best-in-class endpoint protection, detection, and response to digital attacks. Emphasizes a "zero trust" network management strategy and continuous vulnerability assessments.

2. **Advanced Technology Management** — Provides tailored technology consultancy and management services. Focuses on building lasting relationships with clients to ensure high-quality support.

3. **Operational Management** — Offers guidance for informed IT decisions and provides comprehensive monitoring and management of IT systems.

4. **Expertise and Experience** — Over 20 years of experience with a commitment to personalized service, handling over 80 hedge fund clients discreetly.

5. **Intimate Relationships** — Limits client intake to ensure personalized support and builds trust-based relationships with clients.

6. **The 4 C's** — Commitment, Clarity, Connection, and Confidentiality are the guiding principles of their service philosophy.

7. **Additional Services** — Employee monitoring and dark web monitoring to protect against internal and external threats.

Identiom's extensive experience in the sector positions it as a trusted partner, advocating for clients' IT security needs.
