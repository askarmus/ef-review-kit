// EF Review: before/after benchmark template (BenchmarkDotNet).
// Setup:
//   dotnet new console -n EfBench && cd EfBench
//   dotnet add package BenchmarkDotNet
//   dotnet add reference ../YourApp.Data/YourApp.Data.csproj
// Run in Release against a database with realistic data volume (NOT an empty dev DB):
//   dotnet run -c Release
//
// Replace AppDbContext / Orders / Customer with your types. One [Benchmark] for the current
// code (Baseline = true), one per proposed fix.

using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Running;
using Microsoft.EntityFrameworkCore;

BenchmarkRunner.Run<OrderQueryBenchmarks>();

[MemoryDiagnoser]
public class OrderQueryBenchmarks
{
    private DbContextOptions<AppDbContext> _options = default!;
    private List<int> _customerIds = default!;

    [GlobalSetup]
    public void Setup()
    {
        var cs = Environment.GetEnvironmentVariable("EF_BENCH_CS")
                 ?? throw new InvalidOperationException("Set EF_BENCH_CS to a read-only connection string");
        _options = new DbContextOptionsBuilder<AppDbContext>().UseSqlServer(cs).Options;
        using var db = new AppDbContext(_options);
        _customerIds = db.Customers.OrderBy(c => c.Id).Select(c => c.Id).Take(200).ToList();
    }

    // BEFORE: N+1 (EF001)
    [Benchmark(Baseline = true)]
    public async Task<int> Before_NPlusOne()
    {
        await using var db = new AppDbContext(_options);
        var total = 0;
        foreach (var id in _customerIds)
            total += await db.Orders.Where(o => o.CustomerId == id).CountAsync();
        return total;
    }

    // AFTER: one grouped query, no tracking
    [Benchmark]
    public async Task<int> After_SingleQuery()
    {
        await using var db = new AppDbContext(_options);
        var counts = await db.Orders.AsNoTracking()
            .Where(o => _customerIds.Contains(o.CustomerId))
            .GroupBy(o => o.CustomerId)
            .Select(g => g.Count())
            .ToListAsync();
        return counts.Sum();
    }
}

// Also capture logical reads for each variant in SSMS:
//   SET STATISTICS IO ON; SET STATISTICS TIME ON;
// and paste the SQL from query.ToQueryString().
