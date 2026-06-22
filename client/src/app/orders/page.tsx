'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getCurrentUser, getOrders } from '@/utils/auth';
import { ChevronLeft, Package, Clock, MapPin, DollarSign, Calendar, Copy, Check } from 'lucide-react';
import styles from './orders.module.css';

export default function OrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  useEffect(() => {
    async function fetchUserAndOrders() {
      try {
        const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
        if (!token) {
          router.push('/login');
          return;
        }

        const user = await getCurrentUser(token);
        const userOrders = await getOrders(user.user_id);
        
        // Sort orders by date descending
        const sortedOrders = userOrders.sort((a: any, b: any) => {
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });
        
        setOrders(sortedOrders);
      } catch (err) {
        console.error('Failed to fetch orders:', err);
      } finally {
        setLoading(false);
      }
    }

    fetchUserAndOrders();
  }, [router]);

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.spinner}></div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <button className={styles.backBtn} onClick={() => router.push('/support')}>
            <ChevronLeft size={20} /> Back to Support
          </button>
          <h1 className={styles.title}>My Orders</h1>
          <p className={styles.subtitle}>View and track your past orders</p>
        </div>
      </div>

      <div className={styles.mainContent}>
        {orders.length === 0 ? (
          <div className={styles.emptyState}>
            <Package size={48} color="#7a7981" />
            <p>You have no orders yet.</p>
          </div>
        ) : (
          <div className={styles.ordersGrid}>
            {orders.map((order) => (
              <div key={order.order_id} className={styles.orderCard}>
                <div className={styles.cardHeader}>
                  <div className={styles.orderIdContainer}>
                    <div className={styles.orderId}>
                      <Package size={16} />
                      Order ID: {order.order_id.split('-')[0]}...
                    </div>
                    <button 
                      className={styles.copyBtn} 
                      onClick={() => copyToClipboard(order.order_id)}
                      title="Copy full Order ID"
                    >
                      {copiedId === order.order_id ? <Check size={14} color="#22c55e" /> : <Copy size={14} />}
                    </button>
                  </div>
                  <div className={`${styles.statusBadge} ${styles[order.status.replace(/\s+/g, '').toLowerCase()] || styles.defaultStatus}`}>
                    {order.status}
                  </div>
                </div>
                
                <div className={styles.cardBody}>
                  <h3 className={styles.productName}>{order.product_name}</h3>
                  
                  <div className={styles.detailsList}>
                    <div className={styles.detailItem}>
                      <DollarSign size={16} className={styles.detailIcon} />
                      <span>Amount: ${parseFloat(order.total_amount).toFixed(2)}</span>
                    </div>
                    
                    <div className={styles.detailItem}>
                      <Calendar size={16} className={styles.detailIcon} />
                      <span>Ordered: {order.ordered_at ? new Date(order.ordered_at).toLocaleDateString() : 'N/A'}</span>
                    </div>
                    
                    <div className={styles.detailItem}>
                      <Calendar size={16} className={styles.detailIcon} />
                      <span>Delivered: {order.delivered_at ? new Date(order.delivered_at).toLocaleDateString() : 'Pending'}</span>
                    </div>
                    
                    <div className={styles.detailItem}>
                      <MapPin size={16} className={styles.detailIcon} />
                      <span>Shipping to: {order.shipping_address || 'Not provided'}</span>
                    </div>
                  </div>
                </div>
                
                <div className={styles.cardFooter}>
                  <button className={styles.actionBtn} onClick={() => router.push('/support')}>Need Help?</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
