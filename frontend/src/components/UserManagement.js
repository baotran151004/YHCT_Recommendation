import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { FaUserPlus, FaTrash, FaUserMd, FaUserShield, FaArrowLeft } from "react-icons/fa";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../config";

function UserManagement() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  
  // Create user form state
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("doctor");
  const [createLoading, setCreateLoading] = useState(false);
  const [success, setSuccess] = useState("");

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/admin/users`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      } else {
        setError("Không thể tải danh sách người dùng.");
      }
    } catch (err) {
      setError("Lỗi kết nối máy chủ.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (user?.role !== "admin") {
      navigate("/");
      return;
    }
    fetchUsers();
  }, [user, navigate, fetchUsers]);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setCreateLoading(true);
    setSuccess("");
    setError("");

    try {
      const res = await fetch(`${API_URL}/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ username, password, role })
      });

      if (res.ok) {
        setSuccess(`Đã tạo người dùng "${username}" thành công!`);
        setUsername("");
        setPassword("");
        setRole("doctor");
        fetchUsers();
      } else {
        const data = await res.json();
        setError(data.detail || "Không thể tạo người dùng.");
      }
    } catch (err) {
      setError("Lỗi kết nối khi tạo người dùng.");
    } finally {
      setCreateLoading(false);
    }
  };

  const handleDeleteUser = async (targetUserId, targetUsername) => {
    if (!window.confirm(`Bạn có chắc muốn xóa người dùng "${targetUsername}"?`)) return;

    try {
      const res = await fetch(`${API_URL}/admin/users/${targetUserId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });

      if (res.ok) {
        setUsers(users.filter(u => u.user_id !== targetUserId));
      } else {
        const data = await res.json();
        alert(data.detail || "Không thể xóa người dùng.");
      }
    } catch (err) {
      alert("Lỗi kết nối khi xóa người dùng.");
    }
  };

  return (
    <div className="admin-container">
      <div className="admin-header">
        <button className="back-button" onClick={() => navigate("/")}>
          <FaArrowLeft /> Quay lại
        </button>
        <h1>Quản lý người dùng</h1>
      </div>

      <div className="admin-grid">
        {/* Form tạo user */}
        <section className="admin-section create-user-card">
          <h2><FaUserPlus /> Tạo người dùng mới</h2>
          <form onSubmit={handleCreateUser} className="admin-form">
            <div className="form-group">
              <label>Tên đăng nhập</label>
              <input 
                type="text" 
                value={username} 
                onChange={(e) => setUsername(e.target.value)} 
                required 
                placeholder="VD: bs_nguyen"
              />
            </div>
            <div className="form-group">
              <label>Mật khẩu</label>
              <input 
                type="password" 
                value={password} 
                onChange={(e) => setPassword(e.target.value)} 
                required 
                placeholder="********"
              />
            </div>
            <div className="form-group">
              <label>Vai trò</label>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="doctor">Bác sĩ (Doctor)</option>
                <option value="admin">Quản trị viên (Admin)</option>
              </select>
            </div>
            <button type="submit" disabled={createLoading} className="btn-primary">
              {createLoading ? "Đang tạo..." : "Tạo người dùng"}
            </button>
            {success && <p className="success-msg">{success}</p>}
            {error && <p className="error-msg">{error}</p>}
          </form>
        </section>

        {/* Danh sách user */}
        <section className="admin-section user-list-card">
          <h2>Danh sách người dùng</h2>
          {loading ? (
            <p>Đang tải...</p>
          ) : (
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Tên đăng nhập</th>
                    <th>Vai trò</th>
                    <th>Hành động</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.user_id}>
                      <td>{u.username}</td>
                      <td>
                        <span className={`role-badge ${u.role}`}>
                          {u.role === "admin" ? <FaUserShield /> : <FaUserMd />} {u.role}
                        </span>
                      </td>
                      <td>
                        {u.user_id !== user.id && (
                          <button 
                            className="btn-danger" 
                            onClick={() => handleDeleteUser(u.user_id, u.username)}
                          >
                            <FaTrash />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default UserManagement;
