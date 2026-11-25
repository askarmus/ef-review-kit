using Microsoft.EntityFrameworkCore;
namespace Shop.Api.Data;
public class Order { public int Id { get; set; } public int CustomerId { get; set; } public decimal Total { get; set; } public string Status { get; set; } public string Email { get; set; } public DateTime Created { get; set; } public Customer Customer { get; set; } public List<OrderLine> Lines { get; set; } public List<Payment> Payments { get; set; } }
public class Customer { public int Id { get; set; } [MaxLength(100)] public string Name { get; set; } [Precision(18,2)] public decimal Credit { get; set; } public Address Address { get; set; } }
public class OrderLine { public int Id { get; set; } public int OrderId { get; set; } }
public class Payment { public int Id { get; set; } public int OrderId { get; set; } }
public class Address { public string City { get; set; } }
public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> o) : base(o) { }
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<Customer> Customers => Set<Customer>();
    protected override void OnConfiguring(DbContextOptionsBuilder b)
    {
        b.EnableSensitiveDataLogging(); // oops
        b.UseSqlServer("Server=.;Database=Shop;User Id=sa;Password=Pa55word;");
    }
    protected override void OnModelCreating(ModelBuilder mb)
    {
        mb.Entity<Order>().HasMany(o => o.Lines).WithOne().OnDelete(DeleteBehavior.Cascade);
        mb.Entity<Customer>().OwnsOne(c => c.Address);
        mb.Entity<Order>().HasQueryFilter(o => o.Status != "Deleted" && o.CustomerId > 0);
    }
}
