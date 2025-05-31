const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

class GhanaMoFDataScraper {
  constructor() {
    this.baseUrl = 'https://www.mofep.gov.gh';
    this.downloadPath = path.resolve('./ghana_economic_data');
    this.browser = null;
    this.page = null;

    // Priority keywords for research focus
    this.focusKeywords = {
      gdp: ['gdp', 'growth', 'economic growth', 'sectoral', 'agriculture', 'industry', 'services'],
      inflation: ['inflation', 'cpi', 'consumer price', 'cost of living', 'food prices', 'fuel'],
      fiscal: ['budget', 'revenue', 'expenditure', 'deficit', 'surplus', 'tax policy', 'fiscal'],
      debt: ['debt', 'borrowing', 'debt-to-gdp', 'debt service', 'external debt', 'domestic debt'],
      monetary: ['monetary', 'interest rate', 'exchange rate', 'currency', 'cedi'],
      impact: ['crisis', 'reform', 'policy', 'shock', 'covid', 'pandemic', 'global']
    };
  }

  async initialize() {
    // Create download directory
    if (!fs.existsSync(this.downloadPath)) {
      fs.mkdirSync(this.downloadPath, { recursive: true });
    }

    // Create subdirectories for organization by research focus
    const subdirs = [
      'budget_statements',      // Primary source for fiscal data
      'economic_reports',       // GDP, growth, sectoral analysis
      'revenue_reports',        // Tax policy, government revenue
      'debt_reports',          // Public debt analysis
      'monetary_reports',       // Exchange rates, monetary policy
      'inflation_data',         // CPI, cost of living data
      'quarterly_reports',      // Quarterly economic updates
      'annual_reports',         // Annual economic reviews
      'policy_documents'        // Reform and policy impact docs
    ];

    subdirs.forEach(dir => {
      const fullPath = path.join(this.downloadPath, dir);
      if (!fs.existsSync(fullPath)) {
        fs.mkdirSync(fullPath, { recursive: true });
      }
    });

    // Launch browser
    this.browser = await puppeteer.launch({
      headless: false, // Set to true for production
      defaultViewport: null,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    this.page = await this.browser.newPage();

    // Set download behavior
    await this.page._client.send('Page.setDownloadBehavior', {
      behavior: 'allow',
      downloadPath: this.downloadPath
    });

    // Set longer timeout for slow connections
    this.page.setDefaultTimeout(60000);
  }

  // Helper function to categorize documents based on research focus
  categorizeDocument(text, url) {
    const content = (text + ' ' + url).toLowerCase();

    // Priority categorization for research
    if (this.containsKeywords(content, this.focusKeywords.gdp)) {
      return 'economic_reports';
    }
    if (this.containsKeywords(content, this.focusKeywords.inflation)) {
      return 'inflation_data';
    }
    if (this.containsKeywords(content, this.focusKeywords.fiscal)) {
      return 'budget_statements';
    }
    if (this.containsKeywords(content, this.focusKeywords.debt)) {
      return 'debt_reports';
    }
    if (this.containsKeywords(content, this.focusKeywords.monetary)) {
      return 'monetary_reports';
    }
    if (content.includes('quarterly') || content.includes('q1') || content.includes('q2') || content.includes('q3') || content.includes('q4')) {
      return 'quarterly_reports';
    }
    if (content.includes('annual') && !content.includes('budget')) {
      return 'annual_reports';
    }
    if (this.containsKeywords(content, this.focusKeywords.impact)) {
      return 'policy_documents';
    }

    return 'economic_reports'; // Default category
  }

  containsKeywords(content, keywords) {
    return keywords.some(keyword => content.includes(keyword));
  }

  // Enhanced priority scoring for documents
  prioritizeDocument(text, url) {
    const content = (text + ' ' + url).toLowerCase();
    let score = 0;

    // Higher priority for budget statements (key focus)
    if (content.includes('budget statement') || content.includes('economic policy')) score += 10;

    // High priority for annual documents covering the timeframe
    const years = ['2000', '2001', '2002', '2003', '2004', '2005', '2006', '2007', '2008', '2009',
                   '2010', '2011', '2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019',
                   '2020', '2021', '2022', '2023', '2024', '2025'];
    years.forEach(year => {
      if (content.includes(year)) score += 5;
    });

    // Bonus for key economic indicators
    Object.values(this.focusKeywords).flat().forEach(keyword => {
      if (content.includes(keyword)) score += 2;
    });

    return score;
  }

  async downloadBudgetStatements() {
    console.log('📊 Downloading Budget Statements (Priority: Fiscal Analysis)...');

    try {
      await this.page.goto(`${this.baseUrl}/publications/budget-statements`);
      await this.page.waitForSelector('body', { timeout: 30000 });

      // Get all budget statement links with priority scoring
      const budgetLinks = await this.page.evaluate(() => {
        const links = [];

        // Look for PDF links containing budget-related keywords
        const pdfLinks = document.querySelectorAll('a[href*=".pdf"]');
        pdfLinks.forEach(link => {
          const href = link.href;
          const text = link.textContent.trim();

          if (href.includes('budget') || href.includes('Budget') ||
              text.toLowerCase().includes('budget') ||
              text.toLowerCase().includes('economic policy') ||
              text.toLowerCase().includes('fiscal')) {
            links.push({
              url: href,
              text: text,
              type: 'budget_statement'
            });
          }
        });

        return links;
      });

      // Sort by priority for research
      budgetLinks.sort((a, b) => this.prioritizeDocument(b.text, b.url) - this.prioritizeDocument(a.text, a.url));

      console.log(`Found ${budgetLinks.length} budget documents (sorted by relevance)`);

      // Download each budget document to appropriate category
      for (const link of budgetLinks) {
        const category = this.categorizeDocument(link.text, link.url);
        await this.downloadFile(link, category);
      }

      // Focus on specific years for comprehensive coverage
      const priorityYears = [2000, 2005, 2008, 2009, 2012, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
      for (const year of priorityYears) {
        try {
          await this.page.goto(`${this.baseUrl}/budget-statements/${year}`);
          await this.page.waitForSelector('body', { timeout: 10000 });

          const yearLinks = await this.page.evaluate(() => {
            const links = [];
            const pdfLinks = document.querySelectorAll('a[href*=".pdf"]');
            pdfLinks.forEach(link => {
              links.push({
                url: link.href,
                text: link.textContent.trim(),
                type: 'budget_statement'
              });
            });
            return links;
          });

          for (const link of yearLinks) {
            const category = this.categorizeDocument(link.text, link.url);
            await this.downloadFile(link, category);
          }
        } catch (error) {
          console.log(`Budget data for ${year} not found or inaccessible`);
        }
      }

    } catch (error) {
      console.error('Error downloading budget statements:', error);
    }
  }

  async downloadEconomicReports() {
    console.log('📈 Downloading Economic Reports (GDP, Growth, Sectoral Analysis)...');

    try {
      await this.page.goto(`${this.baseUrl}/publications/economic-reports`);
      await this.page.waitForSelector('body', { timeout: 30000 });

      const economicLinks = await this.page.evaluate(() => {
        const links = [];
        const pdfLinks = document.querySelectorAll('a[href*=".pdf"]');

        pdfLinks.forEach(link => {
          const href = link.href;
          const text = link.textContent.trim();

          // Prioritize documents with economic growth and sectoral data
          if (href.includes('economic') || href.includes('Economic') ||
              href.includes('debt') || href.includes('Debt') ||
              text.toLowerCase().includes('economic') ||
              text.toLowerCase().includes('growth') ||
              text.toLowerCase().includes('gdp') ||
              text.toLowerCase().includes('sectoral') ||
              text.toLowerCase().includes('agriculture') ||
              text.toLowerCase().includes('industry') ||
              text.toLowerCase().includes('services') ||
              text.toLowerCase().includes('debt') ||
              text.toLowerCase().includes('development')) {
            links.push({
              url: href,
              text: text,
              type: 'economic_report'
            });
          }
        });

        return links;
      });

      // Sort by relevance to research focus
      economicLinks.sort((a, b) => this.prioritizeDocument(b.text, b.url) - this.prioritizeDocument(a.text, a.url));

      console.log(`Found ${economicLinks.length} economic reports (prioritized for GDP/growth analysis)`);

      for (const link of economicLinks) {
        const category = this.categorizeDocument(link.text, link.url);
        await this.downloadFile(link, category);
      }

    } catch (error) {
      console.error('Error downloading economic reports:', error);
    }
  }

  async downloadBankOfGhanaData() {
    console.log('🏦 Downloading Bank of Ghana Economic Data (Inflation, Monetary Policy)...');

    try {
      // Bank of Ghana has crucial data for inflation and monetary policy analysis
      const bogUrl = 'https://www.bog.gov.gh';

      // Check for Bank of Ghana statistical bulletins and reports
      const bogSections = [
        '/statistics/statistical-bulletins',
        '/monetary-policy/monetary-policy-committee-press-releases',
        '/statistics/key-economic-indicators',
        '/publications/annual-report',
        '/publications/monetary-policy-report'
      ];

      for (const section of bogSections) {
        try {
          await this.page.goto(`${bogUrl}${section}`);
          await this.page.waitForSelector('body', { timeout: 15000 });

          const bogLinks = await this.page.evaluate(() => {
            const links = [];
            const pdfLinks = document.querySelectorAll('a[href*=".pdf"], a[href*=".xlsx"], a[href*=".xls"]');

            pdfLinks.forEach(link => {
              const href = link.href;
              const text = link.textContent.trim();

              // Focus on documents with economic indicators
              if (text.toLowerCase().includes('statistical') ||
                  text.toLowerCase().includes('bulletin') ||
                  text.toLowerCase().includes('monetary') ||
                  text.toLowerCase().includes('inflation') ||
                  text.toLowerCase().includes('exchange') ||
                  text.toLowerCase().includes('economic indicators') ||
                  text.toLowerCase().includes('annual report')) {
                links.push({
                  url: href,
                  text: text,
                  type: 'bog_data'
                });
              }
            });

            return links;
          });

          console.log(`Found ${bogLinks.length} BoG documents in ${section}`);

          for (const link of bogLinks) {
            const category = this.categorizeDocument(link.text, link.url);
            await this.downloadFile(link, category);
          }

        } catch (error) {
          console.log(`Could not access ${section} - may require specific navigation`);
        }
      }

    } catch (error) {
      console.error('Error downloading Bank of Ghana data:', error);
    }
  }

  async downloadStatisticalData() {
    console.log('📊 Downloading Ghana Statistical Service Data (CPI, Inflation, GDP)...');

    try {
      // Ghana Statistical Service has key economic indicators
      const gssUrl = 'https://statsghana.gov.gh';

      const gssSections = [
        '/statistics/economic-statistics/',
        '/statistics/price-statistics/',
        '/gdp-and-growth/',
        '/consumer-price-index/',
        '/publications/'
      ];

      for (const section of gssSections) {
        try {
          await this.page.goto(`${gssUrl}${section}`);
          await this.page.waitForSelector('body', { timeout: 15000 });

          const gssLinks = await this.page.evaluate(() => {
            const links = [];
            const allLinks = document.querySelectorAll('a[href*=".pdf"], a[href*=".xlsx"], a[href*=".xls"], a[href*=".csv"]');

            allLinks.forEach(link => {
              const href = link.href;
              const text = link.textContent.trim();

              // Focus on key economic indicators for research
              if (text.toLowerCase().includes('cpi') ||
                  text.toLowerCase().includes('consumer price') ||
                  text.toLowerCase().includes('inflation') ||
                  text.toLowerCase().includes('gdp') ||
                  text.toLowerCase().includes('gross domestic') ||
                  text.toLowerCase().includes('economic') ||
                  text.toLowerCase().includes('statistical') ||
                  text.toLowerCase().includes('quarterly') ||
                  text.toLowerCase().includes('annual')) {
                links.push({
                  url: href,
                  text: text,
                  type: 'gss_data'
                });
              }
            });

            return links;
          });

          console.log(`Found ${gssLinks.length} GSS documents in ${section}`);

          for (const link of gssLinks) {
            const category = this.categorizeDocument(link.text, link.url);
            await this.downloadFile(link, category);
          }

        } catch (error) {
          console.log(`Could not access GSS ${section}`);
        }
      }

    } catch (error) {
      console.error('Error downloading GSS data:', error);
    }
  }

  async downloadRevenueReports() {
    console.log('💰 Downloading Revenue & Tax Reports...');

    try {
      await this.page.goto(`${this.baseUrl}/publications/revenue-reports`);
      await this.page.waitForSelector('body', { timeout: 30000 });

      const revenueLinks = await this.page.evaluate(() => {
        const links = [];
        const pdfLinks = document.querySelectorAll('a[href*=".pdf"]');

        pdfLinks.forEach(link => {
          links.push({
            url: link.href,
            text: link.textContent.trim(),
            type: 'revenue_report'
          });
        });

        return links;
      });

      console.log(`Found ${revenueLinks.length} revenue reports`);

      for (const link of revenueLinks) {
        await this.downloadFile(link, 'revenue_reports');
      }

    } catch (error) {
      console.error('Error downloading revenue reports:', error);
    }
  }

  async downloadDebtReports() {
    console.log('🏦 Downloading Public Debt Reports...');

    try {
      await this.page.goto(`${this.baseUrl}/investor-relations/annual-public-debt-report`);
      await this.page.waitForSelector('body', { timeout: 30000 });

      const debtLinks = await this.page.evaluate(() => {
        const links = [];
        const pdfLinks = document.querySelectorAll('a[href*=".pdf"]');

        pdfLinks.forEach(link => {
          const href = link.href;
          const text = link.textContent.trim();

          if (href.includes('debt') || href.includes('Debt') ||
              text.toLowerCase().includes('debt')) {
            links.push({
              url: href,
              text: text,
              type: 'debt_report'
            });
          }
        });

        return links;
      });

      console.log(`Found ${debtLinks.length} debt reports`);

      for (const link of debtLinks) {
        await this.downloadFile(link, 'debt_reports');
      }

    } catch (error) {
      console.error('Error downloading debt reports:', error);
    }
  }

  async downloadFinancialSectorReports() {
    console.log('🏧 Downloading Financial Sector Reports...');

    try {
      await this.page.goto(`${this.baseUrl}/publications/financial-sector-reports`);
      await this.page.waitForSelector('body', { timeout: 30000 });

      const financialLinks = await this.page.evaluate(() => {
        const links = [];
        const pdfLinks = document.querySelectorAll('a[href*=".pdf"]');

        pdfLinks.forEach(link => {
          links.push({
            url: link.href,
            text: link.textContent.trim(),
            type: 'financial_report'
          });
        });

        return links;
      });

      console.log(`Found ${financialLinks.length} financial sector reports`);

      for (const link of financialLinks) {
        await this.downloadFile(link, 'financial_sector');
      }

    } catch (error) {
      console.error('Error downloading financial sector reports:', error);
    }
  }

  async downloadIMFWorldBankData() {
    console.log('🌍 Searching for IMF/World Bank Ghana Data References...');

    try {
      // Check for IMF Article IV consultations and World Bank reports
      const internationalSections = [
        '/publications/imf-egdds-data',
        '/news-and-events/imf-updates',
        '/investor-relations'
      ];

      for (const section of internationalSections) {
        try {
          await this.page.goto(`${this.baseUrl}${section}`);
          await this.page.waitForSelector('body', { timeout: 15000 });

          const intlLinks = await this.page.evaluate(() => {
            const links = [];
            const allLinks = document.querySelectorAll('a[href*=".pdf"], a[href*=".xlsx"], a[href*=".xls"]');

            allLinks.forEach(link => {
              const href = link.href;
              const text = link.textContent.trim();

              if (text.toLowerCase().includes('imf') ||
                  text.toLowerCase().includes('world bank') ||
                  text.toLowerCase().includes('article iv') ||
                  text.toLowerCase().includes('consultation') ||
                  text.toLowerCase().includes('staff report') ||
                  text.toLowerCase().includes('economic outlook')) {
                links.push({
                  url: href,
                  text: text,
                  type: 'international_data'
                });
              }
            });

            return links;
          });

          for (const link of intlLinks) {
            const category = this.categorizeDocument(link.text, link.url);
            await this.downloadFile(link, category);
          }

        } catch (error) {
          console.log(`Could not access ${section}`);
        }
      }

    } catch (error) {
      console.error('Error downloading international organization data:', error);
    }
  }

  async downloadQuarterlyReports() {
    console.log('📅 Focusing on Quarterly Economic Reports...');

    try {
      // Search across all publications for quarterly data
      const pages = [
        '/publications/budget-statements',
        '/publications/economic-reports',
        '/publications/revenue-reports'
      ];

      for (const page of pages) {
        await this.page.goto(`${this.baseUrl}${page}`);
        await this.page.waitForSelector('body', { timeout: 15000 });

        const quarterlyLinks = await this.page.evaluate(() => {
          const links = [];
          const allLinks = document.querySelectorAll('a[href*=".pdf"]');

          allLinks.forEach(link => {
            const href = link.href;
            const text = link.textContent.trim().toLowerCase();

            // Look for quarterly patterns
            if (text.includes('quarterly') ||
                text.includes('q1') || text.includes('q2') || text.includes('q3') || text.includes('q4') ||
                text.includes('first quarter') || text.includes('second quarter') ||
                text.includes('third quarter') || text.includes('fourth quarter') ||
                text.includes('mid-year') || text.includes('mid year')) {
              links.push({
                url: href,
                text: link.textContent.trim(),
                type: 'quarterly_report'
              });
            }
          });

          return links;
        });

        for (const link of quarterlyLinks) {
          await this.downloadFile(link, 'quarterly_reports');
        }
      }

    } catch (error) {
      console.error('Error downloading quarterly reports:', error);
    }
  }

  async downloadHistoricalData() {
    console.log('🕰️ Searching for Historical Economic Data (2000-2010)...');

    try {
      // Many older documents might be in archives or different URL patterns
      const historicalYears = [2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010];

      for (const year of historicalYears) {
        try {
          // Try multiple URL patterns for historical data
          const possibleUrls = [
            `${this.baseUrl}/budget-statements/${year}`,
            `${this.baseUrl}/publications/budget-statements/${year}`,
            `${this.baseUrl}/sites/default/files/budget-statements/${year}*`
          ];

          for (const url of possibleUrls) {
            try {
              await this.page.goto(url);
              await this.page.waitForSelector('body', { timeout: 8000 });

              const historicalLinks = await this.page.evaluate((searchYear) => {
                const links = [];
                const allLinks = document.querySelectorAll('a[href*=".pdf"]');

                allLinks.forEach(link => {
                  const href = link.href;
                  const text = link.textContent.trim();

                  if (href.includes(searchYear.toString()) || text.includes(searchYear.toString())) {
                    links.push({
                      url: href,
                      text: text,
                      type: 'historical_data',
                      year: searchYear
                    });
                  }
                });

                return links;
              }, year);

              if (historicalLinks.length > 0) {
                console.log(`Found ${historicalLinks.length} documents for ${year}`);
                for (const link of historicalLinks) {
                  const category = this.categorizeDocument(link.text, link.url);
                  await this.downloadFile(link, category);
                }
                break; // If we found data, no need to try other URL patterns
              }

            } catch (error) {
              // Continue to next URL pattern
            }
          }

        } catch (error) {
          console.log(`No accessible data found for ${year}`);
        }
      }

    } catch (error) {
      console.error('Error downloading historical data:', error);
    }
  }

  async downloadFile(fileInfo, subfolder) {
    try {
      console.log(`Downloading: ${fileInfo.text}`);

      // Extract filename from URL
      const urlParts = fileInfo.url.split('/');
      let filename = urlParts[urlParts.length - 1];

      // Clean filename
      filename = filename.replace(/[<>:"/\\|?*]/g, '_');
      if (!filename.endsWith('.pdf')) {
        filename += '.pdf';
      }

      const filePath = path.join(this.downloadPath, subfolder, filename);

      // Check if file already exists
      if (fs.existsSync(filePath)) {
        console.log(`⏭️  Skipping ${filename} (already exists)`);
        return;
      }

      // Navigate to the file URL
      const response = await this.page.goto(fileInfo.url, { waitUntil: 'networkidle2' });

      if (response && response.ok()) {
        const buffer = await response.buffer();
        fs.writeFileSync(filePath, buffer);
        console.log(`✅ Downloaded: ${filename}`);

        // Add delay between downloads
        await this.page.waitForTimeout(2000);
      } else {
        console.log(`❌ Failed to download: ${fileInfo.text}`);
      }

    } catch (error) {
      console.error(`Error downloading ${fileInfo.text}:`, error);
    }
  }

  async searchForDataFiles() {
    console.log('🔍 Searching for Excel/CSV data files...');

    try {
      // Check for data in specific sections
      const dataSections = [
        '/publications/imf-egdds-data',
        '/investor-relations/public-debt',
        '/publications/petroleum-reports'
      ];

      for (const section of dataSections) {
        try {
          await this.page.goto(`${this.baseUrl}${section}`);
          await this.page.waitForSelector('body', { timeout: 10000 });

          const dataLinks = await this.page.evaluate(() => {
            const links = [];
            const allLinks = document.querySelectorAll('a[href]');

            allLinks.forEach(link => {
              const href = link.href;
              if (href.includes('.xlsx') || href.includes('.xls') ||
                  href.includes('.csv') || href.includes('.json')) {
                links.push({
                  url: href,
                  text: link.textContent.trim(),
                  type: 'data_file'
                });
              }
            });

            return links;
          });

          if (dataLinks.length > 0) {
            console.log(`Found ${dataLinks.length} data files in ${section}`);
            for (const link of dataLinks) {
              await this.downloadFile(link, 'data_files');
            }
          }

        } catch (error) {
          console.log(`No data found in ${section}`);
        }
      }

    } catch (error) {
      console.error('Error searching for data files:', error);
    }
  }

  async generateResearchReport() {
    console.log('📋 Generating Research Analysis Report...');

    const report = {
      projectTitle: "Ghana Economic Growth, Inflation, and Fiscal Trends Analysis (2000-Present)",
      downloadDate: new Date().toISOString(),
      totalFiles: 0,
      dataCategories: {},
      researchFocus: {
        economicGrowth: { files: [], description: "GDP trends, sectoral contributions" },
        inflationData: { files: [], description: "CPI, cost of living, price indices" },
        fiscalPolicy: { files: [], description: "Budget statements, revenue, expenditure" },
        publicDebt: { files: [], description: "Debt trends, debt-to-GDP ratios" },
        monetaryPolicy: { files: [], description: "Interest rates, exchange rates" },
        policyImpact: { files: [], description: "Crisis events, reforms, shocks" }
      },
      nextSteps: [
        "1. Extract time series data from budget statements (2000-2025)",
        "2. Create GDP growth database from economic reports",
        "3. Compile inflation data from BoG and GSS sources",
        "4. Analyze fiscal deficit/surplus trends",
        "5. Map debt-to-GDP progression",
        "6. Identify policy reform impact periods"
      ]
    };

    const subdirs = ['budget_statements', 'economic_reports', 'revenue_reports', 'debt_reports',
                     'monetary_reports', 'inflation_data', 'quarterly_reports', 'annual_reports', 'policy_documents'];

    subdirs.forEach(dir => {
      const fullPath = path.join(this.downloadPath, dir);
      if (fs.existsSync(fullPath)) {
        const files = fs.readdirSync(fullPath);
        report.dataCategories[dir] = {
          count: files.length,
          files: files
        };
        report.totalFiles += files.length;

        // Categorize files by research focus
        files.forEach(file => {
          const filename = file.toLowerCase();
          if (this.containsKeywords(filename, this.focusKeywords.gdp)) {
            report.researchFocus.economicGrowth.files.push(`${dir}/${file}`);
          }
          if (this.containsKeywords(filename, this.focusKeywords.inflation)) {
            report.researchFocus.inflationData.files.push(`${dir}/${file}`);
          }
          if (this.containsKeywords(filename, this.focusKeywords.fiscal)) {
            report.researchFocus.fiscalPolicy.files.push(`${dir}/${file}`);
          }
          if (this.containsKeywords(filename, this.focusKeywords.debt)) {
            report.researchFocus.publicDebt.files.push(`${dir}/${file}`);
          }
          if (this.containsKeywords(filename, this.focusKeywords.monetary)) {
            report.researchFocus.monetaryPolicy.files.push(`${dir}/${file}`);
          }
          if (this.containsKeywords(filename, this.focusKeywords.impact)) {
            report.researchFocus.policyImpact.files.push(`${dir}/${file}`);
          }
        });
      }
    });

    // Generate research analysis guide
    const analysisGuide = `# Ghana Economic Analysis - Data Collection Report

## Project Overview
**Title:** ${report.projectTitle}
**Collection Date:** ${new Date().toLocaleDateString()}
**Total Documents:** ${report.totalFiles}

## Research Focus Areas & Available Data

### 1. Economic Growth Analysis
- **Files Available:** ${report.researchFocus.economicGrowth.files.length}
- **Key Sources:** Budget statements, economic reports, quarterly bulletins
- **Focus:** GDP trends, sectoral contributions (agriculture, industry, services)

### 2. Inflation & Cost of Living
- **Files Available:** ${report.researchFocus.inflationData.files.length}
- **Key Sources:** Bank of Ghana reports, GSS price statistics
- **Focus:** CPI trends, food vs non-food inflation

### 3. Fiscal Policy Analysis
- **Files Available:** ${report.researchFocus.fiscalPolicy.files.length}
- **Key Sources:** Annual budget statements, mid-year reviews
- **Focus:** Revenue/expenditure trends, deficit/surplus analysis

### 4. Public Debt Trends
- **Files Available:** ${report.researchFocus.publicDebt.files.length}
- **Key Sources:** Annual debt reports, economic policy documents
- **Focus:** Debt-to-GDP ratios, debt service burden

### 5. Monetary Policy Impact
- **Files Available:** ${report.researchFocus.monetaryPolicy.files.length}
- **Key Sources:** Bank of Ghana monetary policy reports
- **Focus:** Interest rates, exchange rate trends

## Data by Category
${Object.entries(report.dataCategories).map(([category, data]) => 
  `- **${category}**: ${data.count} files`).join('\n')}

## Recommended Analysis Workflow

### Phase 1: Data Extraction (Weeks 1-2)
1. **Budget Statements Analysis:**
   - Extract annual GDP figures (2000-2025)
   - Compile government revenue and expenditure data
   - Track fiscal deficit/surplus trends

2. **Inflation Data Compilation:**
   - Extract CPI data from BoG reports
   - Identify food vs non-food price trends
   - Map exchange rate impacts on inflation

### Phase 2: Time Series Construction (Weeks 3-4)
1. Create standardized datasets for:
   - Real GDP growth rates (annual & quarterly)
   - Inflation rates by category
   - Government fiscal indicators
   - Debt metrics

### Phase 3: Impact Analysis (Weeks 5-6)
1. **Major Events Analysis:**
   - 2008 Global Financial Crisis impact
   - 2011-2012 Oil production effects
   - 2020 COVID-19 pandemic response
   - Recent debt restructuring impacts

### Phase 4: Synthesis & Reporting (Weeks 7-8)
1. Trend analysis and visualization
2. Policy effectiveness assessment
3. Recommendations for sustainable growth

## Key Files to Prioritize

### Highest Priority (Start Here):
${report.researchFocus.fiscalPolicy.files.slice(0, 5).map(file => `- ${file}`).join('\n')}

### Economic Growth Data:
${report.researchFocus.economicGrowth.files.slice(0, 5).map(file => `- ${file}`).join('\n')}

### Inflation Analysis:
${report.researchFocus.inflationData.files.slice(0, 5).map(file => `- ${file}`).join('\n')}

## Tools Recommended for Analysis
- **PDF Data Extraction:** Tabula, Adobe Acrobat, or Python (pdfplumber)
- **Data Analysis:** Python (pandas), R, or Excel
- **Visualization:** Tableau, Python (matplotlib/seaborn), or R (ggplot2)
- **Time Series Analysis:** Python (statsmodels) or R (forecast)

## Notes
- Focus on annual data first, then add quarterly granularity
- Pay attention to methodology changes across years
- Cross-reference MoF data with BoG and GSS statistics
- Consider real vs nominal figures for inflation analysis
`;

    const reportPath = path.join(this.downloadPath, 'research_analysis_report.json');
    const guidePath = path.join(this.downloadPath, 'research_analysis_guide.md');

    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    fs.writeFileSync(guidePath, analysisGuide);

    console.log(`\n📊 RESEARCH DATA COLLECTION SUMMARY:`);
    console.log(`📈 Economic Growth Files: ${report.researchFocus.economicGrowth.files.length}`);
    console.log(`💰 Inflation Data Files: ${report.researchFocus.inflationData.files.length}`);
    console.log(`🏛️ Fiscal Policy Files: ${report.researchFocus.fiscalPolicy.files.length}`);
    console.log(`💳 Public Debt Files: ${report.researchFocus.publicDebt.files.length}`);
    console.log(`🏦 Monetary Policy Files: ${report.researchFocus.monetaryPolicy.files.length}`);
    console.log(`📋 Total Files: ${report.totalFiles}`);
  }

  async close() {
    if (this.browser) {
      await this.browser.close();
    }
  }

  async scrapeAll() {
    try {
      await this.initialize();

      console.log('🚀 Starting Ghana Economic Analysis Data Collection...');
      console.log('🎯 Focus: Economic Growth, Inflation, Fiscal Policy, Debt Analysis (2000-2025)');
      console.log(`📁 Download directory: ${this.downloadPath}\n`);

      // Priority order based on research focus
      console.log('Phase 1: Core Fiscal and Budget Data');
      await this.downloadBudgetStatements();

      console.log('\nPhase 2: Historical Data Collection (2000-2010)');
      await this.downloadHistoricalData();

      console.log('\nPhase 3: Economic Growth and Sectoral Analysis');
      await this.downloadEconomicReports();

      console.log('\nPhase 4: Quarterly Economic Indicators');
      await this.downloadQuarterlyReports();

      console.log('\nPhase 5: Inflation and Monetary Policy Data');
      await this.downloadBankOfGhanaData();

      console.log('\nPhase 6: Statistical Indicators (CPI, GDP)');
      await this.downloadStatisticalData();

      console.log('\nPhase 7: Revenue and Tax Policy Analysis');
      await this.downloadRevenueReports();

      console.log('\nPhase 8: Public Debt Analysis');
      await this.downloadDebtReports();

      console.log('\nPhase 9: International Organization Reports');
      await this.downloadIMFWorldBankData();

      console.log('\nPhase 10: Additional Financial Reports');
      await this.downloadFinancialSectorReports();

      console.log('\nPhase 11: Searching for Raw Data Files');
      await this.searchForDataFiles();

      await this.generateResearchReport();

      console.log('\n🎉 Data collection completed successfully!');
      console.log('📋 Check the research_analysis_guide.md for your next steps');
      console.log('📊 Review research_analysis_report.json for detailed file categorization');

    } catch (error) {
      console.error('Error during scraping:', error);
    } finally {
      await this.close();
    }
  }
}

// Usage
async function main() {
  const scraper = new GhanaMoFDataScraper();
  await scraper.scrapeAll();
}

// Uncomment to run
// main().catch(console.error);

module.exports = GhanaMoFDataScraper;