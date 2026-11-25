using Microsoft.EntityFrameworkCore;
using Shop.Api.Data;
namespace Shop.Api.Services;
public class OrderService
{
    private readonly AppDbContext _db;
    private static AppDbContext _cached;
    public OrderService(AppDbContext db) { _db = db; }

    public async Task<List<Order>> GetOrdersWithCustomers(List<int> ids)
    {
        var orders = await _db.Orders.Where(o => ids.Contains(o.Id)).ToListAsync();
        foreach (var o in orders)
        {
            o.Customer = await _db.Customers.FirstOrDefaultAsync(c => c.Id == o.CustomerId);
        }
        return orders;
    }

    public List<Order> GetActive()
    {
        // "http://not-a-comment" test
        var url = "http://x";
        return _db.Orders.ToList().Where(o => o.Status == "Active").Take(20).ToList();
    }

    public async Task<List<Order>> GetAllOrders()
    {
        return await _db.Orders.ToListAsync();
    }

    public async Task<bool> HasOrders(int customerId)
    {
        var list = _db.Orders.Where(o => o.CustomerId == customerId).ToList();
        return _db.Orders.Count(o => o.CustomerId == customerId) > 0;
    }

    public async Task Import(List<Order> items)
    {
        foreach (var item in items)
        {
            _db.Orders.Add(item);
            await _db.SaveChangesAsync();
        }
    }

    public List<Order> Search(string name, string email)
    {
        var sql = "SELECT * FROM Orders WHERE Email = '" + email + "'";
        var a = _db.Orders.FromSqlRaw(sql).ToList();
        var b = _db.Orders.FromSqlRaw($"SELECT * FROM Orders WHERE Status = '{name}'").ToList();
        var safe = _db.Orders.FromSql($"SELECT * FROM Orders WHERE Status = {name}").ToList();
        return _db.Orders.Where(o => o.Email.ToLower() == email.ToLower()).ToList();
    }

    public Order GetDetails(int id)
    {
        return _db.Orders.Include(o => o.Lines).Include(o => o.Payments).Include(o => o.Customer).First(o => o.Id == id);
    }

    public void Archive(DateTime cutoff)
    {
        var old = _db.Orders.Where(o => o.Created < cutoff).ToList();
        foreach (var o in old)
        {
            o.Status = "Archived";
        }
        _db.SaveChanges();
        _db.Orders.RemoveRange(_db.Orders.Where(o => o.Status == "Deleted").ToList());
    }

    public Order Latest() => _db.Orders.OrderByDescending(o => o.Created).First();

    public Order Newest()
    {
        return _db.Orders.OrderByDescending(o => o.Created).FirstOrDefault();
    }

    public int Blocking() => _db.Orders.CountAsync().Result;

    public async Task Twice(Order o)
    {
        _db.Orders.Add(o);
        await _db.SaveChangesAsync();
        o.Status = "Paid";
        await _db.SaveChangesAsync();
    }

    public async Task Both()
    {
        await Task.WhenAll(_db.Orders.ToListAsync(), _db.Customers.ToListAsync());
    }

    public IQueryable<Order> Query() => _db.Orders;

    public IQueryable<Order> QueryAll()
    {
        return _db.Orders.IgnoreQueryFilters();
    }

    // GOOD code: should not be flagged
    public async Task<List<Order>> GetPage(int page, CancellationToken ct)
    {
        return await _db.Orders.AsNoTracking().Where(o => o.Status == "Open").OrderBy(o => o.Id).Skip(page * 20).Take(20).ToListAsync(ct);
    }
}
