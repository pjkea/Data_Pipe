const GhanaMoFDataScraper = require('./ghana_mof_scraper.js');

async function main() {
    console.log('🚀 Starting Ghana MoF Data Collection...');

    const scraper = new GhanaMoFDataScraper();
    await scraper.scrapeAll();

    console.log('✅ Data collection completed!');
}

// Run the scraper
main().catch(console.error);