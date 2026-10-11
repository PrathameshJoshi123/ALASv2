"use client";

import { useState } from "react";
import { User, Bell } from "lucide-react";
import toast from "react-hot-toast";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("profile");
  const [loading, setLoading] = useState(false);

  const [profileData, setProfileData] = useState({
    name: "Senior Associate",
    email: "associate@lexington.com",
  });

  const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setProfileData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleSaveProfile = async () => {
    setLoading(true);
    try {
      toast.success("Profile updated successfully");
    } catch (error) {
      toast.error("Failed to update profile");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-600 mt-1">
          Manage your account and preferences
        </p>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow border border-slate-200 overflow-hidden">
        <div className="flex border-b border-slate-200">
          {[
            { id: "profile", label: "Profile", icon: User },
            { id: "notifications", label: "Notifications", icon: Bell },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-6 py-4 font-medium border-b-2 transition ${
                  activeTab === tab.id
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="p-8">
          {/* Profile Tab */}
          {activeTab === "profile" && (
            <div className="space-y-6 max-w-2xl">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Full Name
                </label>
                <input
                  type="text"
                  name="name"
                  value={profileData.name}
                  onChange={handleProfileChange}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  name="email"
                  value={profileData.email}
                  disabled
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg bg-slate-50 text-slate-600 cursor-not-allowed"
                />
                <p className="text-xs text-slate-600 mt-1">
                  Email cannot be changed
                </p>
              </div>

              <button
                onClick={handleSaveProfile}
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium px-6 py-2 rounded-lg transition"
              >
                {loading ? "Saving..." : "Save Changes"}
              </button>
            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === "notifications" && (
            <div className="space-y-6 max-w-2xl">
              <div className="space-y-4">
                {[
                  { label: "Contract uploaded", id: "upload" },
                  { label: "Analysis complete", id: "analysis" },
                  { label: "High risk detected", id: "risk" },
                  { label: "Team invitations", id: "invites" },
                ].map((notification) => (
                  <label
                    key={notification.id}
                    className="flex items-center gap-3 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      defaultChecked
                      className="rounded w-4 h-4"
                    />
                    <span className="text-slate-700">{notification.label}</span>
                  </label>
                ))}
              </div>

              <button className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-2 rounded-lg transition">
                Save Preferences
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Account Info */}
      <div className="bg-slate-50 rounded-lg border border-slate-200 p-6">
        <h3 className="font-semibold text-slate-900 mb-3">
          Account Information
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-slate-600">Organization</p>
            <p className="text-slate-900 font-medium">Lexington & Co</p>
          </div>
          <div>
            <p className="text-slate-600">Membership</p>
            <p className="text-slate-900 font-medium">Active (Enterprise)</p>
          </div>
        </div>
      </div>
    </div>
  );
}
