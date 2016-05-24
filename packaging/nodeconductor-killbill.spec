Name: nodeconductor-killbill
Summary: KillBill plugin for NodeConductor
Group: Development/Libraries
Version: 0.3.3
Release: 1.el7
License: Copyright 2015 OpenNode LLC. All rights reserved.
Url: http://nodeconductor.com
Source0: %{name}-%{version}.tar.gz

Requires: nodeconductor >= 0.79.0
Requires: python-lxml >= 3.2.0
Requires: python-xhtml2pdf >= 0.0.6

BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot

BuildRequires: python-setuptools

%description
NodeConductor KillBill allows to make invoices via KillBill.

%prep
%setup -q -n %{name}-%{version}

%build
python setup.py build

%install
rm -rf %{buildroot}
python setup.py install --single-version-externally-managed -O1 --root=%{buildroot} --record=INSTALLED_FILES

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%defattr(-,root,root)

%changelog
* Thu Apr 28 2016 Jenkins <jenkins@opennodecloud.com> - 0.3.3-1.el7
- New upstream release

* Tue Dec 8 2015 Jenkins <jenkins@opennodecloud.com> - 0.3.2-1.el7
- New upstream release

* Thu Nov 19 2015 Roman Kosenko <roman@opennodecloud.com> - 0.1.0-1.el7
- Initial version of the package
