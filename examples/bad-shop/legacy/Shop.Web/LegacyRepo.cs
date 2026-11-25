public class ShopEntities : DbContext { public DbSet<Product> Products { get; set; } }
public class Product { public int Id { get; set; } public virtual ICollection<Tag> Tags { get; set; } }
public class LegacyRepo
{
    public List<Product> Find(string n)
    {
        var ctx = new ShopEntities();
        return ctx.Database.SqlQuery<Product>("SELECT * FROM Products WHERE Name = '" + n + "'").ToList();
    }
}
