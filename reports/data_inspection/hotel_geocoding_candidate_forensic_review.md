# Candidate Forensic Review Report

## 1. Executive Summary
This report presents a forensic analysis of the 9 geocoding candidates retrieved for the 20-hotel deterministic sample under the newly integrated pipeline. The analysis reveals that the core classification policy (Day 2.8B thresholds) is robust; however, two specific implementation bugs are causing failures. First, the `HotelQueryNormalizer` overly strips critical identifiers (producing empty query strings in some edge cases). Second, the similarity check unfairly compares the short source name against the full Nominatim `display_name` (which includes the full postal address), artificially dragging down the score of legitimate matches to <0.30 and classifying them as "invalid". No canonical datasets or databases were modified during this diagnostic.

## 2. 20-Hotel Retrieval Statistics
- **Total Hotels Processed:** 20
- **Total Candidates Retrieved:** 9
- **Hotels with Candidates:** 4
- **Resolved:** 0
- **Ambiguous:** 0
- **Rejected:** 0
- **Invalid:** 4
- **Not Found:** 16 (Includes hotels that retrieved candidates but scored 0 in resolution)

## 3. Complete 9-Candidate Table

| Hotel ID | Original Name | Normalized Name | Hotel City | Hotel Address | Query Used | Candidate Name (Truncated) | Cand. City | Cand. Lat/Lon | Name Sim | City Match | Addr Match | Final Class | Reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 105 | Collection O 812451 The Grand Budget Hotel | The Grand | Bangalore | Karnataka, Bangalore | The Grand Bangalore | Bangalore Express, City of London... | City of London | 51.5129, -0.0850 | 0.27 | False | False | invalid | Name similarity too low |
| 90 | OYO Hotel Fiesta Grand | Hotel Fiesta Grand | Bangalore | Near Mariyappa Road... | Hotel Fiesta Grand Bangalore | OYO Hotel Fiesta Grand, T. Mariyappa... | Bengaluru | 12.9418, 77.5854 | 0.20 | False | False | invalid | Name similarity too low |
| 605 | OYO Rooms 026 Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh Karol Bagh | Karol Bagh, Pusa Road, Paharganj... | Delhi | 28.6440, 77.1885 | 0.35 | False | True | invalid | Name similarity too low |
| 605 | OYO Rooms 026 Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh Karol Bagh | Karol Bagh, Pusa Road, Paharganj... | Delhi | 28.6439, 77.1890 | 0.35 | False | True | invalid | Name similarity too low |
| 605 | OYO Rooms 026 Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh Karol Bagh | Karol Bagh, Pusa Road, Paharganj... | Delhi | 28.6439, 77.1885 | 0.35 | False | True | invalid | Name similarity too low |
| 605 | OYO Rooms 026 Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh Karol Bagh | Karol Bagh (Telephone Exchange)... | Delhi | 28.6431, 77.1815 | 0.27 | False | True | invalid | Name similarity too low |
| 617 | OYO Rooms 108 Near Karol Bagh Metro Station 1 |  | Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh, Delhi, Central Delhi... | Delhi | 28.6529, 77.1890 | 0.23 | False | True | invalid | Name similarity too low |
| 617 | OYO Rooms 108 Near Karol Bagh Metro Station 1 |  | Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh, Pusa Road, Paharganj... | Delhi | 28.6440, 77.1885 | 0.40 | False | True | invalid | Name similarity too low |
| 617 | OYO Rooms 108 Near Karol Bagh Metro Station 1 |  | Karol Bagh | Karol Bagh | Karol Bagh | Karol Bagh, Delhi, Central Delhi... | Delhi | 28.6388, 77.1616 | 0.23 | False | True | invalid | Name similarity too low |

## 4. Case-by-Case Analysis & Root Cause Classification

- **Hotel 105 (The Grand vs Bangalore Express):**
  - **Category:** B. Incorrect candidate correctly rejected.
  - **Root Cause:** Due to a generic name and poor locality, the query "The Grand Bangalore" returned a generic place in London. It was rightfully rejected.

- **Hotel 90 (OYO Hotel Fiesta Grand):**
  - **Category:** A. Correct candidate rejected because matching logic is too strict.
  - **Root Cause:** It found the exact exact match (OYO Hotel Fiesta Grand on T. Mariyappa Road). However, `Candidate Name` is parsed as the full Nominatim `display_name` (e.g. "OYO Hotel Fiesta Grand, T. Mariyappa Road..."). The similarity function compares "OYO Hotel Fiesta Grand" to the 150+ character string, producing a similarity of `0.20`. 

- **Hotel 605 (OYO Rooms 026 Karol Bagh):**
  - **Category:** D. Poor query / insufficient candidate retrieval.
  - **Root Cause:** The query "Karol Bagh" just returns the Karol Bagh neighborhood in Delhi. The number `026` was stripped out, leaving only the neighborhood name, making resolution impossible. The candidates are correctly marked invalid because they are neighborhoods, not the hotel. 

- **Hotel 617 (OYO Rooms 108 Near Karol Bagh Metro Station 1):**
  - **Category:** D. Poor query / insufficient candidate retrieval.
  - **Root Cause:** The `HotelQueryNormalizer` identified "OYO Rooms", "108", "Near Karol Bagh Metro Station", and "1" as promotional/metadata components and stripped them ALL. The result was an empty string for `normalized_name`, generating a generic query "Karol Bagh" that hits neighborhood results.

## 5. Entities & Normalization Policy Validation

- **Is the matching policy valid?**
  Yes, the threshold logic (0.85 for names, checking cities, etc.) is perfectly valid. "DO NOT change matching thresholds simply to increase the resolved count."
- **Does query normalization need modification?**
  Yes. The normalizer is improperly stripping ALL context from edge cases like Hotel 617 (resolving to an empty string) by removing numbers and phrases that happen to constitute the entire unique hotel name. We recommend adding a safety check to ensure it doesn't reduce a string to zero length. 

## 6. Specific Recommended Changes

1. **Bugfix in Candidate Name Extraction:** In `scripts/resolve_all_hotel_coordinates.py`, extract the candidate's venue name by grabbing `cand.get('display_name', '').split(',')[0].strip()` instead of taking the entire comma-separated address for similarity comparison.
2. **Bugfix in Normalizer:** In `app/data/hotel_query_normalizer.py`, keep track of the string state. If a regex replacement reduces the string to empty or whitespace, do not apply that regex.

## 7. Next Steps
We recommend proceeding to implement the two bugfixes (name parsing + normalizer safety guard) and updating integration tests accordingly. No canonical data was modified or migrated during this step.
