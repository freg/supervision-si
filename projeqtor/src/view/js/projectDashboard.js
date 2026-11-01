/**
 * Project Dashboard JS
 */

var progressChartParameters = [
  'workProgressDashboard',
  'budgetProgressDashboard',
  'risksProgressDashboard',
  'technicalProgressDashboard',
  'financialProgressDashboard',
  'ticketsProgressDashboard',
  'requirementsProgressDashboard',
  'userStoriesProgressDashboard'
];

function initializeProgressChartHistory() {
  dojo.xhrGet({
    url: "../tool/getParamDashboard.php?key=progressChartActivationOrder" + addTokenIndexToUrl(),
    handleAs: "text",
    load: function(data, __args__) {
      try {
        if (data && data !== '' && data !== 'null') {
          var savedOrder = JSON.parse(data);
          if (Array.isArray(savedOrder)) {
            progressChartActivationOrder = savedOrder;
          }
        } else {
          buildInitialProgressChartHistory();
        }
      } catch (error) {
        buildInitialProgressChartHistory();
      }
    },
    error: function(error) {
      buildInitialProgressChartHistory();
    }
  });
}
function buildInitialProgressChartHistory() {
  progressChartActivationOrder = [];
  progressChartParameters.forEach(function(paramName) {
    var widget = dijit.byId(paramName);
    if (widget && widget.get('value') === 'on') {
      progressChartActivationOrder.push(paramName);
    }
  });
  if (progressChartActivationOrder.length > 3) {
    var toKeep = progressChartActivationOrder.slice(0, 3);
    var toDeactivate = progressChartActivationOrder.slice(3);
    
    toDeactivate.forEach(function(paramName) {
      var widget = dijit.byId(paramName);
      if (widget) {
        widget.set('value', 'off', false);
        saveDataToSession(paramName, 'off', false);
        applyParameterVisibility(paramName, false);
      }
    });
    
    progressChartActivationOrder = toKeep;
  }
  saveProgressChartHistory();
}

function saveProgressChartHistory() {
  var historyString = JSON.stringify(progressChartActivationOrder);
  saveDataToSession('progressChartActivationOrder', historyString, false);
}

function refreshProjectDashboardList() {
  var countStatus = dojo.byId('countStatusProjectDashboard').value;
  for (var i = 1; i <= countStatus; i++) {
    var checkbox = dijit.byId('showStatusProjectDashboard' + i);
    if (checkbox) {
      saveDataToSession('showStatus' + checkbox.value + 'ProjectDashboard', 
                       checkbox.checked ? 'true' : 'false', true);
    }
  }
  applyCurrentFilters();
}

function applyStatusFilter(selectedStatuses) {
  var barFilter = dojo.byId('barFilterByStatus');
  var isBarVisible = barFilter && barFilter.style.display !== 'none';
  if (!isBarVisible) {
    selectedStatuses = [];
  }
  var showClosed = getDashboardParameter('closedProjectDashboard');
  var showPaused = getDashboardParameter('pausedProjectsDashboard');
  var showNotStarted = getDashboardParameter('notStartedProjects');
  
  var allTiles = document.querySelectorAll('.project-tile');
  var vItemList = dbd.getProjectList();
  
  allTiles.forEach(function(tile) {
    var projectId = tile.getAttribute('data-project-id');
    var project = vItemList.find(function(p) { return p.getId() == projectId; });
    
    if (project) {
      var isIdle = (project.getIdle() == 1 || project.getIdle() == '1' || project.getIdle() === true);
      var isPaused = (project.getPaused() == 1 || project.getPaused() == '1' || project.getPaused() === true);
      var isNotStarted = (project.getHandled() == 0 || project.getHandled() == '0' || project.getHandled() === false);

      var shouldHideByVisibility = false;
      if (isIdle && !showClosed) shouldHideByVisibility = true;
      if (isPaused && !showPaused) shouldHideByVisibility = true;
      if (isNotStarted && !showNotStarted) shouldHideByVisibility = true;
      
      if (shouldHideByVisibility) {
        dojo.addClass(tile, 'projectItemHide');
        tile.style.display = 'none';
        return;
      }
      var projectStatus = project.getStatus();
      var projectStatusId = projectStatus ? projectStatus.id : null;
      
      var shouldShowByStatus = !isBarVisible ||
                               selectedStatuses.length === 0 || 
                               (projectStatusId && selectedStatuses.indexOf(projectStatusId.toString()) !== -1);
      
      if (shouldShowByStatus) {
        dojo.removeClass(tile, 'projectItemHide');
        tile.style.display = 'block';
      } else {
        dojo.addClass(tile, 'projectItemHide');
        tile.style.display = 'none';
      }
    }
  });
  applyCurrentFilters();
}
  
function updateShowStatusStateProjectDashboard(element, statusNum, color) {
  var checkbox = dijit.byId('showStatusProjectDashboard' + statusNum);
  if (checkbox) {
    checkbox.set('checked', !checkbox.checked);
    if (checkbox.checked) {
      element.className = 'docLineTagNew';
      element.style.backgroundColor = color;
      element.style.color = getForeColor(color);
    } else {
      element.className = 'docLineTag';
      element.style.backgroundColor = '';
      element.style.color = '';
    } 
    refreshProjectDashboardList();
  }
}

function getActiveProgressCharts(excludeParam) {
  var active = [];
  progressChartParameters.forEach(function(paramName) {
    if (excludeParam && paramName === excludeParam) return;
    var widget = dijit.byId(paramName);
    if (widget && widget.get('value') === 'on') {
      active.push(paramName);
    }
  });
  return active;
}

function enforceProgressChartLimit(changedParam, newValue) {
  if (progressChartParameters.indexOf(changedParam) === -1) return true;
  
  if (newValue === 'off') {
    var index = progressChartActivationOrder.indexOf(changedParam);
    if (index > -1) {
      progressChartActivationOrder.splice(index, 1);
    }
    saveProgressChartHistory();
    return true;
  }
  var existingIndex = progressChartActivationOrder.indexOf(changedParam);
  if (existingIndex > -1) {
    progressChartActivationOrder.splice(existingIndex, 1);
  }
  progressChartActivationOrder.push(changedParam);
  if (progressChartActivationOrder.length > 3) {
    var oldestActive = progressChartActivationOrder.shift();
    var oldestWidget = dijit.byId(oldestActive);
    if (oldestWidget) {
      oldestWidget.set('value', 'off', false);
      saveDataToSession(oldestActive, 'off', false);
      applyParameterVisibility(oldestActive, false);
    }
  }
  saveProgressChartHistory();
  return true;
}

function getJsonDashboardData(onlyName) {
  if (onlyName === undefined) onlyName = false;
  var data = dojo.byId('projectDashboardJsonData');
  if (onlyName) data = 'projectDashboardJsonData';
  return data;
}

function refreshDashboard() {
  var url = '../tool/jsonProjectDashboard.php';
  var jsonDiv = getJsonDashboardData(true);
  var callback = function() {
    drawProjectDashboard(false);
  }; 
  loadContent(url, jsonDiv, null, false, callback);
}

function saveLayoutRecording() {
  var layoutSelect = dijit.byId('layoutRecording');
  if (!layoutSelect) {
    showAlert(i18n('pleaseSelectLayout'));
    return;
  }
  var selectedLayout = layoutSelect.get('value');
  if (!selectedLayout) {
    showAlert(i18n('pleaseSelectLayout'));
    return;
  }
  var parametersToSave = [
    'datesStartDashboard',
    'datesEndDashboard',
    'statusDashboard',
    'priorityDashboard',
    'nextMilestoneDashboard',
    'weatherDashboard',
    'trendDashboard',
    'qualityDashboard',
    'timelineDashboard',
    'workProgressDashboard',
    'budgetProgressDashboard',
    'risksProgressDashboard',
    'technicalProgressDashboard',
    'financialProgressDashboard',
    'ticketsProgressDashboard',
    'requirementsProgressDashboard',
    'userStoriesProgressDashboard',
    'closedProjectDashboard',
    'pausedProjectsDashboard',
    'notStartedProjects',
    'colorMilestone',
    'linearViewDashboard'
  ];
  var paramValues = {};
  parametersToSave.forEach(function(paramName) {
    var widget = dijit.byId(paramName);
    if (widget) {
      paramValues[paramName] = widget.get('value');
    }
  });
  var listShowMilestoneWidget = dijit.byId('listShowMilestone');
  if (listShowMilestoneWidget) {
    paramValues['listShowMilestone'] = listShowMilestoneWidget.get('value');
  }
  var orderByWidget = dijit.byId('dashboardOrderBy');
  if (orderByWidget) {
    paramValues['dashboardOrderBy'] = orderByWidget.get('value');
    if (orderByWidget.get('value') === 'priority') {
      var prioritySwitch = dijit.byId('priorityDashboard');
      if (prioritySwitch && prioritySwitch.get('value') !== 'on') {
        prioritySwitch.set('value', 'on');
        enhancedSwitchHandler('priorityDashboard', 'on', false);
      }
      paramValues['priorityDashboard'] = 'on';
    }
  }
  paramValues['progressChartActivationOrder'] = JSON.stringify(progressChartActivationOrder);
  var paramString = JSON.stringify(paramValues);
  var sessionKey = 'paramLayout_' + selectedLayout;
  saveDataToSession(sessionKey, paramString, true);
  showAlert(i18n('layoutSavedSuccessfully'));
}

function restoreLayoutRecording(layoutName) {
  if (!layoutName || layoutName === '' || layoutName === ' ') {
    return;
  }
  var sessionKey = 'paramLayout_' + layoutName;
  dojo.xhrGet({
    url: "../tool/getParamDashboard.php?key=" + sessionKey + addTokenIndexToUrl(),
    handleAs: "text",
    load: function(data, __args__) {
      try {
        if (!data || data === '' || data === 'null') {
          showAlert(i18n('noParamSaved'));
          return;
        }
        var params = JSON.parse(data);
        
        if (params.hasOwnProperty('progressChartActivationOrder')) {
          try {
            var savedOrder = JSON.parse(params['progressChartActivationOrder']);
            if (Array.isArray(savedOrder)) {
              progressChartActivationOrder = savedOrder;
              saveProgressChartHistory();
            }
          } catch (e) {
            console.error('progressChartActivationOrder error :', e);
          }
        }
        
        var viewModeChanged = false;
        var currentLinearView = getDashboardParameter('linearViewDashboard');
        
        for (var paramName in params) {
          if (params.hasOwnProperty(paramName) && paramName !== 'progressChartActivationOrder') {
            var value = params[paramName];
            var widget = dijit.byId(paramName);
            if (widget) {
              if (paramName === 'linearViewDashboard') {
                var newLinearView = (value === 'on');
                if (currentLinearView !== newLinearView) {
                  viewModeChanged = true;
                }
              }
              
              widget.set('value', value);
              if (paramName === 'dashboardOrderBy') {
                saveDataToSession('dashboardOrderBy', value, true);
                if (value === 'priority') {
                  enhancedSwitchHandler('priorityDashboard', true, true);
                }
              } else {
                saveDataToSession(paramName, value, true);
                if (paramName !== 'listShowMilestone' && paramName !== 'linearViewDashboard') {
                  var isVisible = (value === 'on');
                  applyParameterVisibility(paramName, isVisible);
                }
              }
            }
          }
        }
        
        if (viewModeChanged) {
          drawProjectDashboard(false);
        }
        
      } catch (error) {
        console.error(error);
      }
    },
  });
}

function onSearchByLayoutChange(newLayout) {
  saveDataToSession('searchByLayout', newLayout, false);
  restoreLayoutRecording(newLayout);
}

function initializeLayoutRecording() {
  var addRecordingButton = dojo.byId('addRecordingDashboard');
  if (addRecordingButton) {
    dojo.connect(addRecordingButton, 'onclick', function(evt) {
      saveLayoutRecording();
    });
  }
  var searchByLayoutWidget = dijit.byId('searchByLayout');
  if (searchByLayoutWidget) {
    dojo.connect(searchByLayoutWidget, 'onChange', function(value) {
      onSearchByLayoutChange(value);
    });
  }
}

function getDashboardParameter(paramName) {
  var switchWidget = dijit.byId(paramName);
  if (switchWidget) {
    return switchWidget.get('value') === 'on';
  }
  return false;
}

function applyParameterVisibility(paramName, isVisible) {
  var displayValue = 'none';
  if (isVisible) {
    if (paramName == 'nextMilestoneDashboard' ||  paramName == 'priorityDashboard') {
      displayValue = 'flex';
    } else {
      displayValue = 'block';
    }
  }
  
  needsChartResize = false;
  var isLinearView = getDashboardParameter('linearViewDashboard');
  
  switch(paramName) {
    case 'datesStartDashboard':
      var startDateRows = document.querySelectorAll('.date-row.date-start');
      startDateRows.forEach(function(row) {
        row.style.display = displayValue;
      });
      break;
      
    case 'datesEndDashboard':
      var endDateRows = document.querySelectorAll('.date-row.date-end');
      endDateRows.forEach(function(row) {
        row.style.display = displayValue;
      });
      break;
      
    case 'statusDashboard':
      var statusSelector = isLinearView ? '.row-status' : '.project-status';
      var statusElements = document.querySelectorAll(statusSelector);
      statusElements.forEach(function(elem) {
        elem.style.display = displayValue;
      });
	  needsChartResize = isLinearView ? true:false;
      break;
    
    case 'priorityDashboard':
      var prioritySelector = isLinearView ? '.row-priority' : '.tile-priority';
      var statusElements = document.querySelectorAll(prioritySelector);
      statusElements.forEach(function(elem) {
        elem.style.display = displayValue;
      });
	  needsChartResize = isLinearView ? true:false;
      break;
    
    case 'nextMilestoneDashboard':
      var milestoneSelector = isLinearView ? '.row-milestone' : '.tile-next-milestone';
      var milestoneElements = document.querySelectorAll(milestoneSelector);
      milestoneElements.forEach(function(elem) {
        elem.style.display = displayValue;
      });
	  needsChartResize = isLinearView ? true:false;
      break;
      
    case 'weatherDashboard':
      var weatherElements = document.querySelectorAll('.tile-weather, .row-weather');
      weatherElements.forEach(function(elem) {
        elem.style.display = displayValue;
        if (isVisible) {
		  elem.style.display = 'flex';
          elem.style.width = '36px';
          elem.style.height = '24px';
          elem.style.alignItems = 'center';
          elem.style.justifyContent = 'center';
        }
      });
      break;
      
    case 'trendDashboard':
      var trendElements = document.querySelectorAll('.tile-trend, .row-trend');
      trendElements.forEach(function(elem) {
        elem.style.display = displayValue;
        if (isVisible) {
		  elem.style.display = 'flex';
          elem.style.width = '36px';
          elem.style.height = '24px';
          elem.style.alignItems = 'center';
          elem.style.justifyContent = 'center';
        }
      });
      break;
      
    case 'qualityDashboard':
      var qualityElements = document.querySelectorAll('.tile-quality, .row-quality');
      qualityElements.forEach(function(elem) {
        elem.style.display = displayValue;
		if (isVisible) {
		  elem.style.display = 'flex';
		  elem.style.width = '36px';
		  elem.style.height = '24px';
		  elem.style.alignItems = 'center';
		  elem.style.justifyContent = 'center';
		}
      });
      break;
      
    case 'resourcesDashboard':
      var resourcesElements = document.querySelectorAll('.tile-resources');
      resourcesElements.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'timelineDashboard':
      var timelineSelector = isLinearView ? '.row-timeline' : '.tile-timeline';
      var timelineElements = document.querySelectorAll(timelineSelector);
      timelineElements.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'colorMilestone':
      drawProjectDashboard(false);
      break;
      
	case 'workProgressDashboard':
	  var progressElements = document.querySelectorAll('.tile-work-progress');
	  progressElements.forEach(function(elem) {
	    elem.style.display = displayValue;
	  });
	  if (isLinearView) {
	    document.querySelectorAll('.row-progress').forEach(function(container) {
	      var canvasDiv = container.querySelector('.tile-work-progress');
	      if (canvasDiv) {
	        canvasDiv.style.display = displayValue;
	      }
	    });
	  }
	  needsChartResize = true;
	  break;
	    
	case 'budgetProgressDashboard':
	  var budgetElements = document.querySelectorAll('.tile-budget-progress');
	  budgetElements.forEach(function(elem) {
	    elem.style.display = displayValue;
	  });
	  if (isLinearView) {
	    document.querySelectorAll('.row-progress').forEach(function(container) {
	      var canvasDiv = container.querySelector('.tile-budget-progress');
	      if (canvasDiv) {
	        canvasDiv.style.display = displayValue;
	      }
	    });
	  }
	  needsChartResize = true;
	  break;
	    
	case 'risksProgressDashboard':
	  var risksElements = document.querySelectorAll('.tile-risks-progress');
	  risksElements.forEach(function(elem) {
	    elem.style.display = displayValue;
	  });
	  if (isLinearView) {
	    document.querySelectorAll('.row-progress').forEach(function(container) {
	      var canvasDiv = container.querySelector('.tile-risks-progress');
	      if (canvasDiv) {
	        canvasDiv.style.display = displayValue;
	      }
	    });
	  }
	  needsChartResize = true;
	  break;
	    
	case 'technicalProgressDashboard':
	  var technicalElements = document.querySelectorAll('.tile-technical-progress');
	  technicalElements.forEach(function(elem) {
	    elem.style.display = displayValue;
	  });
	  if (isLinearView) {
	    document.querySelectorAll('.row-progress').forEach(function(container) {
	      var canvasDiv = container.querySelector('.tile-technical-progress');
	      if (canvasDiv) {
	        canvasDiv.style.display = displayValue;
	      }
	    });
	  }
	  needsChartResize = true;
	  break;
	    
	case 'financialProgressDashboard':
	  var financialElements = document.querySelectorAll('.tile-financial-progress');
	  financialElements.forEach(function(elem) {
	    elem.style.display = displayValue;
	  });
	  if (isLinearView) {
	    document.querySelectorAll('.row-progress').forEach(function(container) {
	      var canvasDiv = container.querySelector('.tile-financial-progress');
	      if (canvasDiv) {
	        canvasDiv.style.display = displayValue;
	      }
	    });
	  }
	  needsChartResize = true;
	  break;
	          
	case 'ticketsProgressDashboard':
	  var ticketsElements = document.querySelectorAll('.tile-tickets-progress');
	  ticketsElements.forEach(function(elem) {
	    elem.style.display = displayValue;
	  });
	  if (isLinearView) {
	    document.querySelectorAll('.row-progress').forEach(function(container) {
	      var canvasDiv = container.querySelector('.tile-tickets-progress');
	      if (canvasDiv) {
	        canvasDiv.style.display = displayValue;
	      }
	    });
	  }
	  needsChartResize = true;
	  break;
	          
	case 'requirementsProgressDashboard':
	  var requirementsElements = document.querySelectorAll('.tile-requirements-progress');
	  requirementsElements.forEach(function(elem) {
	    elem.style.display = displayValue;
	  });
	  if (isLinearView) {
	    document.querySelectorAll('.row-progress').forEach(function(container) {
	      var canvasDiv = container.querySelector('.tile-requirements-progress');
	      if (canvasDiv) {
	        canvasDiv.style.display = displayValue;
	      }
	    });
	  }
	  needsChartResize = true;
	  break;
	          
	case 'userStoriesProgressDashboard':
	  var userStoriesElements = document.querySelectorAll('.tile-userstories-progress');
	  userStoriesElements.forEach(function(elem) {
	    elem.style.display = displayValue;
	  });
	  if (isLinearView) {
	    document.querySelectorAll('.row-progress').forEach(function(container) {
	      var canvasDiv = container.querySelector('.tile-userstories-progress');
	      if (canvasDiv) {
	        canvasDiv.style.display = displayValue;
	      }
	    });
	  }
	  needsChartResize = true;
	  break;
      
    case 'closedProjectDashboard':
    case 'pausedProjectsDashboard':
    case 'notStartedProjects':
      var allTiles = document.querySelectorAll('.project-tile, .project-row');
      var vItemList = dbd.getProjectList();
      var showClosed = getDashboardParameter('closedProjectDashboard');
      var showPaused = getDashboardParameter('pausedProjectsDashboard');
      var showNotStarted = getDashboardParameter('notStartedProjects');
      allTiles.forEach(function(tile) {
        var projectId = tile.getAttribute('data-project-id');
        var project = vItemList.find(function(p) { return p.getId() == projectId; });
        if (project) {
          var isIdle = (project.getIdle() == 1 || project.getIdle() == '1' || project.getIdle() === true);
          var isPaused = (project.getPaused() == 1 || project.getPaused() == '1' || project.getPaused() === true);
          var isNotStarted = (project.getHandled() == 0 || project.getHandled() == '0' || project.getHandled() === false);
          var shouldHide = false;
          if (isIdle && !showClosed) shouldHide = true;
          if (isPaused && !showPaused) shouldHide = true;
          if (isNotStarted && !showNotStarted) shouldHide = true;
          var showDisplay = tile.classList.contains('project-row') ? 'flex' : 'block';
          tile.style.display = shouldHide ? 'none' : showDisplay;
        }
      });
      updateStatusBarAvailability();
      applyCurrentFilters();
      break;
  }
  
  if (needsChartResize) {
    var allElements = document.querySelectorAll('.project-tile, .project-row');
    allElements.forEach(function(element) {
      adjustChartSizes(element);
      redrawChartsForTile(element);
//	  if (getDashboardParameter('linearViewDashboard')){
//		var params = getDashboardParameters();
//		var progressChartsVisible = params.showWorkProgress || params.showBudgetProgress || params.showRisksProgress || params.showTechnicalProgress || params.showFinancialProgress || params.showTicketsProgress || params.showRequirementsProgress || params.showUserStoriesProgress;
//		var minHeight = progressChartsVisible ? '70px' : '70px';
//		var projectRows = document.querySelectorAll('.project-row');
//		projectRows.forEach(function(row) {
//		  row.style.minHeight = minHeight;
//		});
//	   }

    });
  }
}

function updateStatusBarAvailability() {
  var showClosed = getDashboardParameter('closedProjectDashboard');
  var showPaused = getDashboardParameter('pausedProjectsDashboard');
  var showNotStarted = getDashboardParameter('notStartedProjects');
  
  var vItemList = dbd.getProjectList();
  if (!vItemList || vItemList.length === 0) return;
  
  var statusCount = {};
  for (var i = 0; i < vItemList.length; i++) {
    var project = vItemList[i];
    var isIdle = (project.getIdle() == 1 || project.getIdle() == '1' || project.getIdle() === true);
    var isPaused = (project.getPaused() == 1 || project.getPaused() == '1' || project.getPaused() === true);
    var isNotStarted = (project.getHandled() == 0 || project.getHandled() == '0' || project.getHandled() === false);  
    var shouldExclude = false;
    if (isIdle && !showClosed) shouldExclude = true;
    if (isPaused && !showPaused) shouldExclude = true;
    if (isNotStarted && !showNotStarted) shouldExclude = true;
    if (!shouldExclude) {
      var status = project.getStatus();
      if (status && status.id) {
        var statusId = status.id.toString();
        statusCount[statusId] = (statusCount[statusId] || 0) + 1;
      }
    }
  }
  var statusContainers = document.querySelectorAll('.status-tag-container');
  var hasChanges = false;
  
  statusContainers.forEach(function(container) {
    var statusId = container.getAttribute('data-status-id');
    var checkbox = container.querySelector('input[type="checkbox"]');
    var statusTag = container.querySelector('span[class*="docLineTag"]');
    if (statusCount[statusId] && statusCount[statusId] > 0) {
      container.style.display = 'inline-block';
      if (statusTag) {
        statusTag.style.opacity = '1';
        statusTag.style.pointerEvents = 'auto';
      }
    } else {
      container.style.display = 'none';
      if (checkbox) {
        var checkboxWidget = dijit.byId(checkbox.id);
        if (checkboxWidget && checkboxWidget.get('checked')) {
          checkboxWidget.set('checked', false);
          saveDataToSession('showStatus' + statusId + 'ProjectDashboard', 'false', true);
          if (statusTag) {
            statusTag.className = 'docLineTag';
            statusTag.style.backgroundColor = '';
            statusTag.style.color = '';
          }
          
          hasChanges = true;
        }
      }
    }
  });
  
  if (hasChanges) {
    setTimeout(function() {
      applyCurrentFilters();
    }, 50);
  }
}

function handleDatesMutualExclusivity(changedParam, newValue) {
  if (changedParam === 'datesStartDashboard') {
    if (newValue === 'on') {
      var datesEndSwitch = dijit.byId('datesEndDashboard');
      if (datesEndSwitch && datesEndSwitch.get('value') === 'on') {
        datesEndSwitch.set('value', 'off');
        saveDataToSession('datesEndDashboard', 'off', true);
        applyParameterVisibility('datesEndDashboard', false);
      }
    }
  } else if (changedParam === 'datesEndDashboard') {
    if (newValue === 'on') {
      var datesStartSwitch = dijit.byId('datesStartDashboard');
      if (datesStartSwitch && datesStartSwitch.get('value') === 'on') {
        datesStartSwitch.set('value', 'off');
        saveDataToSession('datesStartDashboard', 'off', true);
        applyParameterVisibility('datesStartDashboard', false);
      }
    }
  }
}

function enhancedSwitchHandler(paramName, newValue, completeRefresh) {
  if (completeRefresh === undefined) completeRefresh = false;
  enforceProgressChartLimit(paramName, newValue);
  var isVisible = (newValue === 'on');
  handleDatesMutualExclusivity(paramName, newValue);
  saveDataToSession(paramName, newValue, true); 
  if (completeRefresh) {
    refreshDashboard();
  } else {
    applyParameterVisibility(paramName, isVisible);
  }
}

function toggleDashboardParameter(paramName) {
  var switchWidget = dijit.byId(paramName);
  if (switchWidget) {
    var currentValue = switchWidget.get('value');
    var newValue = (currentValue === 'on') ? 'off' : 'on';
    switchWidget.set('value', newValue);
  }
}

function filterDashboard() {
  applyCurrentFilters();  
}

function applyCurrentFilters() {
  var idResponsible = dijit.byId('searchByResponsible').get('value');
  var idClient = dijit.byId('searchByClient').get('value');
  var idOrganization = dijit.byId('searchByOrganization').get('value');
  
  idResponsible = idResponsible ? idResponsible.toString().trim() : '';
  idClient = idClient ? idClient.toString().trim() : '';
  idOrganization = idOrganization ? idOrganization.toString().trim() : '';
 
  var showClosed = getDashboardParameter('closedProjectDashboard');
  var showPaused = getDashboardParameter('pausedProjectsDashboard');
  var showNotStarted = getDashboardParameter('notStartedProjects');
  
  var selectedStatuses = [];
  var barFilter = dojo.byId('barFilterByStatus');
  var isBarVisible = barFilter && barFilter.style.display !== 'none';
  
  if (isBarVisible) {
    var countStatus = dojo.byId('countStatusProjectDashboard');
    if (countStatus) {
      var count = countStatus.value;
      for (var i = 1; i <= count; i++) {
        var checkbox = dijit.byId('showStatusProjectDashboard' + i);
        if (checkbox && checkbox.checked) {
          selectedStatuses.push(checkbox.value);
        }
      }
    }
  }
 
  var isLinearView = getDashboardParameter('linearViewDashboard');
  var vItemList = dbd.getProjectList();
  
  for (var j = 0; j < vItemList.length; j++) {
    var project = vItemList[j];
    var projectId = project.getId();
    
    var itemNode = null;
    if (isLinearView) {
      itemNode = dojo.byId('projectRow_' + projectId);
    } else {
      itemNode = dojo.byId('project_' + projectId);
    }
    
    if (!itemNode) continue;
    
    var itemResp = project.getIdManager();
    var itemClient = project.getIdClient();
    var itemOrganization = project.getIdOrganization();
    var itemStatus = project.getStatus();
    var itemStatusId = itemStatus ? itemStatus.id : null;
    
    var isIdle = (project.getIdle() == 1 || project.getIdle() == '1' || project.getIdle() === true);
    var isPaused = (project.getPaused() == 1 || project.getPaused() == '1' || project.getPaused() === true);
    var isNotStarted = (project.getHandled() == 0 || project.getHandled() == '0' || project.getHandled() === false);
    
    var okByVisibilityParams = true;
    if (isIdle && !showClosed) okByVisibilityParams = false;
    if (isPaused && !showPaused) okByVisibilityParams = false;
    if (isNotStarted && !showNotStarted) okByVisibilityParams = false;
    
    if (!okByVisibilityParams) {
      dojo.addClass(itemNode, 'projectItemHide');
      itemNode.style.display = 'none';
      continue;
    }
    
    var okResp = (!idResponsible) || (itemResp == idResponsible);
    var okClient = (!idClient) || (itemClient == idClient);
    var okOrganization = (!idOrganization) || (itemOrganization == idOrganization);
    
    var okStatus = !isBarVisible || 
                   selectedStatuses.length === 0 || 
                   (itemStatusId && selectedStatuses.indexOf(itemStatusId.toString()) !== -1);
 
    var showDisplay = isLinearView ? 'flex' : 'block';
    
    if (okResp && okClient && okOrganization && okStatus) {
      dojo.removeClass(itemNode, 'projectItemHide');
      itemNode.style.display = showDisplay;
    } else {
      dojo.addClass(itemNode, 'projectItemHide');
      itemNode.style.display = 'none';
    }
  }
}

function changeDashboardOrderBy() {
  var orderBy = dijit.byId('dashboardOrderBy').get('value')
  if (window.dbd) {
    window.dbd.Draw();
  }
}


function getMilestoneFilter() {
  var widget = dijit.byId('listShowMilestone');
  if (widget) {
    var value = widget.get('value');
    return value && value !== ' ' ? value : null;
  }
  return null;
}

// Milestone idMilestoneType
function filterMilestonesByType(milestones, filterType) {
  if (!milestones || milestones.length === 0) return [];
  if (!filterType || filterType === ' ' || filterType === '') return [];
  if (filterType === 'all') return milestones;
  var filtered = milestones.filter(function(milestone) {
    var match = milestone.idtype && milestone.idtype.toString() === filterType.toString();
    return match;
  });
  return filtered;
}

function getNextMilestoneFiltered(milestones, filterType) {
  if (!milestones || milestones.length === 0) {
    return null;
  }
  var filteredMilestones = filterMilestonesByType(milestones, filterType);
  for (var i = 0; i < filteredMilestones.length; i++) {
    if (filteredMilestones[i].done === 0 || filteredMilestones[i].done === '0') {
      return filteredMilestones[i];
    }
  }
  return null;
}

// Next milestone by idMilestoneType not done
function getMilestoneFilter() {
  var widget = dijit.byId('listShowMilestone');
  if (widget) {
    var value = widget.get('value');
    if (!value || value === ' ' || value === '') {
      return null;
    }
    return value;
  }
  return null;
}

function onMilestoneFilterChange(newValue) {
  saveDataToSession('listShowMilestone', newValue, true);
  drawProjectDashboard(false);
}


function darkenColor(hex, percent) {
  hex = hex.replace('#','');
  let r = parseInt(hex.substring(0,2), 16);
  let g = parseInt(hex.substring(2,4), 16);
  let b = parseInt(hex.substring(4,6), 16);

  r = Math.floor(r * (100 - percent) / 100);
  g = Math.floor(g * (100 - percent) / 100);
  b = Math.floor(b * (100 - percent) / 100);

  return "#" + r.toString(16).padStart(2,'0')
             + g.toString(16).padStart(2,'0')
             + b.toString(16).padStart(2,'0');
}

function initMilestoneFilterListener() {
  var milestoneFilterWidget = dijit.byId('listShowMilestone');
  if (milestoneFilterWidget) {
    if (milestoneFilterWidget._milestoneChangeHandle) {
      dojo.disconnect(milestoneFilterWidget._milestoneChangeHandle);
    }
    milestoneFilterWidget._milestoneChangeHandle = dojo.connect(milestoneFilterWidget, 'onChange', function(value) {
      onMilestoneFilterChange(value);
    });
  }
}

function onMilestoneFilterChange(newValue) {
  saveDataToSession('listShowMilestone', newValue, true);
  setTimeout(function() {
    drawProjectDashboard(false);
  }, 100);
}
var JSDashboard; 
if (!JSDashboard) JSDashboard = {};

// ==================== OBJET DASHBOARD ====================
JSDashboard.Dashboard = function() {
  var vProjectList = new Array();
  
  this.AddProject = function(value) {
    vProjectList.push(value);
  };
  
  this.getProjectList = function() { 
    return vProjectList; 
  };
  
  this.clearProjects = function() {
    vProjectList = [];
  };
  
  // Draw dashboard
  this.Draw = function() {
    window.top.showWait();
    
    var container = dojo.byId('divProjectDashboardContent');
    if (!container) {
      console.error('Container divProjectDashboardContent not found');
      window.top.hideWait();
      return;
    }
    
    dijit.registry.findWidgets(container).forEach(function(widget) {
      try {
        widget.destroyRecursive();
      } catch(e) {
        console.warn('Error destroying widget:', e);
      }
    });
    
    container.innerHTML = '';
    
    if (vProjectList.length === 0) {
      container.innerHTML = '<div style="text-align:center;padding:50px;color:#666;">'+i18n('noDataFound')+'</div>';
      window.top.hideWait();
      return;
    }
    
    var orderByWidget = dijit.byId('dashboardOrderBy');
    if (orderByWidget) {
      var orderBy = orderByWidget.get('value');
      if (orderBy) {
        vProjectList.sort(function(a, b) {
          switch(orderBy) {
            case 'wbs':
              return (a.getWbs() || '').localeCompare(b.getWbs() || '');
            case 'name':
              return (a.getName() || '').localeCompare(b.getName() || '');
            case 'work':
              var workA = parseFloat(a.getWorkPlanned()) || parseFloat(a.getWorkValidated()) || null;
              var workB = parseFloat(b.getWorkPlanned()) || parseFloat(b.getWorkValidated()) || null;
              if (workA === null && workB === null) return 0;
              if (workA === null) return 1;
              if (workB === null) return -1;
              return workB - workA;
            case 'priority':
              return (parseInt(a.getPriority()) || 9999) - (parseInt(b.getPriority()) || 9999);
			  case 'EndDate':
			    var dateValuesA = a.getTimelineDateValues();
			    var dateValuesB = b.getTimelineDateValues();
			    var dateA = parseDate(dateValuesA.realEndDate || dateValuesA.plannedEndDate || dateValuesA.validatedEndDate);
			    var dateB = parseDate(dateValuesB.realEndDate || dateValuesB.plannedEndDate || dateValuesB.validatedEndDate);
			    if (dateA === null && dateB === null) return 0;
			    if (dateA === null) return 1; 
			    if (dateB === null) return -1;
			    return dateA - dateB;
			  case 'recents':
				var dateA = parseDate(a.getTimelineDateValues().creationDate);
				var dateB = parseDate(b.getTimelineDateValues().creationDate);
			    if (dateA === null && dateB === null) return 0;
				if (dateA === null) return 1;
				if (dateB === null) return -1;
				return dateB - dateA;
            default:
              return 0;
          }
        });
      }
    }

    var isLinearView = getDashboardParameter('linearViewDashboard');
    var tilesHtml = '<div class="dashboard-tiles-container ' + (isLinearView ? 'linear-view' : 'card-view') + '">';
    
    // Create each tile 
    for (var i = 0; i < vProjectList.length; i++) {
      var project = vProjectList[i];
      tilesHtml += project.drawTile();
    }
    tilesHtml += '</div>';
    container.innerHTML = tilesHtml;
    dojo.parser.parse(container);
    
    for (var i = 0; i < vProjectList.length; i++) {
      var project = vProjectList[i];
      
      var elementSelector = isLinearView ? '.project-row[data-project-id="' + project.getId() + '"]' : '.project-tile[data-project-id="' + project.getId() + '"]';
      var tileElement = container.querySelector(elementSelector);
      if (!tileElement) continue;
      
      // Timeline
      var timelineId = "timeline-" + project.getId();
      var timelineCanvas = document.getElementById(timelineId);
      if (timelineCanvas) {
        let elementProject = document.getElementById(isLinearView ? "projectRow_" + project.getId() : "project_" + project.getId());
        let valueProject = elementProject.getAttribute("data-typeMilestone");
        var filteredMilestones = filterMilestonesByType(project.getMilestones(), valueProject);
        var useColorMilestone = getDashboardParameter('colorMilestone');
        createTimeline(timelineId, project.getValidatedStartDate(), project.getPlannedStartDate(), project.getRealStartDate(),
                      project.getValidatedEndDate(), project.getPlannedEndDate(), project.getRealEndDate(), filteredMilestones, useColorMilestone, project.getTimelineDateValues());
      }
      
      // ResizeObserver 
      if (tileElement.chartResizeObserver) {
        tileElement.chartResizeObserver.disconnect();
      }
      tileElement.chartResizeObserver = new ResizeObserver(() => {
        adjustChartSizes(tileElement);
        redrawChartsForTile(tileElement);
      });
      tileElement.chartResizeObserver.observe(tileElement);
        
      // Tooltips 
      setupTooltipsForProject(project, isLinearView);
    }
    
    var menuSelector = isLinearView ? '.row-menu-container' : '.tile-menu-container';
    document.querySelectorAll(menuSelector).forEach(function(menuContainer) {
      const btn = menuContainer.querySelector(isLinearView ? '.row-menu-btn' : '.tile-menu-btn');
      const dropdown = menuContainer.querySelector(isLinearView ? '.row-menu-dropdown' : '.tile-menu-dropdown');
      
      if (!dropdown) return;
      
      menuContainer.addEventListener('mouseenter', function() {
        dropdown.style.opacity = '1';
        dropdown.style.visibility = 'visible';
        dropdown.style.transform = 'translateY(0)';
      });
      
      menuContainer.addEventListener('mouseleave', function() {
        dropdown.style.opacity = '0';
        dropdown.style.visibility = 'hidden';
        dropdown.style.transform = 'translateY(-10px)';
      });
      
      menuContainer.addEventListener('click', function(e) {
        e.stopPropagation();
      });
    });
    
    setTimeout(function() {
      for (var i = 0; i < vProjectList.length; i++) {
        var project = vProjectList[i];
        var elementSelector = isLinearView ? '.project-row[data-project-id="' + project.getId() + '"]' : '.project-tile[data-project-id="' + project.getId() + '"]';
        var tileElement = container.querySelector(elementSelector);
        if (!tileElement) continue;

        if (!isLinearView) {
          adjustChartSizes(tileElement);
        }
        
        // Work progress
        var workProgressId = "workProgress-" + project.getId();
        var workProgressCanvas = document.getElementById(workProgressId);
        if (workProgressCanvas) {
          progressChart(workProgressCanvas, project.getWorkValidated(), project.getWorkReal(), 
                       project.getWorkLeft(), project.getWorkPlanned(), 'workProgressCanvas', 
                       '<div class="iconImputation16 imageColorNewGui iconImputation iconSize16"></div>');
        }
        
        // Budget progress
        var budgetProgressId = "budgetProgress-" + project.getId();
        var budgetProgressCanvas = document.getElementById(budgetProgressId);
        if (budgetProgressCanvas) {
          progressChart(budgetProgressCanvas, project.getTotalValidatedCost(), project.getTotalRealCost(), 
                       project.getTotalLeftCost(), project.getTotalPlannedCost(), 'budgetProgressCanvas', 
                       '<div class="iconExpenses16 imageColorNewGui iconExpenses iconSize16"></div>');
        }
        
        // Risks progress
        var risksProgressId = "risksProgress-" + project.getId();
        var risksProgressCanvas = document.getElementById(risksProgressId);
        if (risksProgressCanvas) {
          progressChartStatus(risksProgressCanvas, project.getClosedRisk(), project.getDoneRisk(), 
                             project.getTodoRisk(), project.getTotalRisk(), 'riskProgressCanvas', 
                             '<div class="iconCriticality16 imageColorNewGui iconCriticality iconSize16"></div>');
        }
        
        // Technical progress
        var technicalProgressId = "technicalProgress-" + project.getId();
        var technicalProgressCanvas = document.getElementById(technicalProgressId);
        if (technicalProgressCanvas) {
          progressChart(technicalProgressCanvas, project.getUnitToRealise(), project.getUnitRealised(), 
                       project.getUnitLeft(), project.getUnitProgress(), 'technicalProgressCanvas', 
                       '<div class="iconProgress16 imageColorNewGui iconProgress iconSize16"></div>');
        }
        
        // Financial progress
        var financialProgressId = "financialProgress-" + project.getId();
        var financialProgressCanvas = document.getElementById(financialProgressId);
        if (financialProgressCanvas) {
          progressChart(financialProgressCanvas, project.getRevenue(), project.getInvoiced(), 
                       project.getToBeBilled(), project.getPlannedFinancial(), 'financialProgressCanvas', 
                       '<div class="iconBill16 imageColorNewGui iconBill iconSize16"></div>');
        }
        
        // Tickets progress
        var ticketsProgressId = "ticketsProgress-" + project.getId();
        var ticketsProgressCanvas = document.getElementById(ticketsProgressId);
        if (ticketsProgressCanvas) {
          progressChartStatus(ticketsProgressCanvas, project.getClosedTicket(), project.getDoneTicket(), 
                             project.getTodoTicket(), project.getTotalTicket(), 'ticketProgressCanvas', 
                             '<div class="iconTicket16 imageColorNewGui iconTicket iconSize16"></div>');
        }
        
        // Requirements progress
        var requirementsProgressId = "requirementsProgress-" + project.getId();
        var requirementsProgressCanvas = document.getElementById(requirementsProgressId);
        if (requirementsProgressCanvas) {
          progressChartStatus(requirementsProgressCanvas, project.getClosedRequirement(), project.getDoneRequirement(), 
                             project.getTodoRequirement(), project.getTotalRequirement(), 'requirementProgressCanvas', 
                             '<div class="iconRequirement16 imageColorNewGui iconRequirement iconSize16"></div>');
        }
        
        // User Stories progress
        var userStoriesProgressId = "userStoriesProgress-" + project.getId();
        var userStoriesProgressCanvas = document.getElementById(userStoriesProgressId);
        if (userStoriesProgressCanvas) {
          progressChartStatus(userStoriesProgressCanvas, project.getClosedUserStory(), project.getDoneUserStory(), 
                             project.getTodoUserStory(), project.getTotalUserStory(), 'userStoryProgressCanvas', 
                             '<div class="iconUserStory16 imageColorNewGui iconUserStory iconSize16"></div>');
        }
      }
    }, 100);
    
    applyCurrentFilters();
    updateStatusBarAvailability();

    window.top.hideWait();
  };
};

function getDashboardParameters() {
  return {
    showDatesStart: getDashboardParameter('datesStartDashboard'),
    showDatesEnd: getDashboardParameter('datesEndDashboard'),
    showStatus: getDashboardParameter('statusDashboard'),
    showPriority: getDashboardParameter('priorityDashboard'),
    showNextMilestone: getDashboardParameter('nextMilestoneDashboard'),
    showWeather: getDashboardParameter('weatherDashboard'),
    showTrend: getDashboardParameter('trendDashboard'),
    showQuality: getDashboardParameter('qualityDashboard'),
    showResources: getDashboardParameter('resourcesDashboard'),
    showTimeline: getDashboardParameter('timelineDashboard'),
    colorMilestone: getDashboardParameter('colorMilestone'),
    showWorkProgress: getDashboardParameter('workProgressDashboard'),
    showBudgetProgress: getDashboardParameter('budgetProgressDashboard'),
    showRisksProgress: getDashboardParameter('risksProgressDashboard'),
    showTechnicalProgress: getDashboardParameter('technicalProgressDashboard'),
    showFinancialProgress: getDashboardParameter('financialProgressDashboard'),
    showTicketsProgress: getDashboardParameter('ticketsProgressDashboard'),
    showRequirementsProgress: getDashboardParameter('requirementsProgressDashboard'),
    showUserStoriesProgress: getDashboardParameter('userStoriesProgressDashboard'),
    showClosedProject: getDashboardParameter('closedProjectDashboard'),
    showPausedProject: getDashboardParameter('pausedProjectsDashboard'),
    showNotStartedProjects: getDashboardParameter('notStartedProjects')
  };
}

// ==================== OBJET PROJECT ====================
JSDashboard.Project = function(pProject) {
  formatProjectDashboardDisplayDates(pProject);
  var vId = pProject.id;
  var vName = pProject.name;
  var vColor = pProject.color || '#999999';
  var vWbs = pProject.wbs;
  var vPriority = pProject.priority;
  var vPaused = pProject.paused;
  var vIdle = pProject.idle;
  var vHandled = pProject.handled;
  var vFile = pProject.photo;
  var vLastAtt =pProject.lastatt;
  var vIdPhoto = pProject.idphoto;

  //dates
  var vValidatedStartDate = pProject.validatedstartdate;
  var vPlannedStartDate = pProject.plannedstartdate;
  var vRealStartDate = pProject.realstartdate;
  var vValidatedEndDate = pProject.validatedenddate;
  var vPlannedEndDate = pProject.plannedenddate;
  var vRealEndDate = pProject.realenddate;
  var vCreationDate = pProject.creationdate;
  var vTimelineDateValues = getTimelineDateValues(pProject);
  
  var vWorkValidated = pProject.validatedwork;
  var vWorkReal = pProject.realwork;
  var vWorkPlanned = pProject.plannedwork;
  var vWorkLeft = pProject.leftwork;
  
  var vTotalValidatedCost = pProject.totalvalidatedcost;
  var vTotalRealCost = pProject.totalrealcost;
  var vTotalPlannedCost = pProject.totalplannedcost;
  var vTotalLeftCost = pProject.totalleftcost;
  
  var vRisk = pProject.risk;
  var vClosedRisk = vRisk.closed;
  var vTodoRisk = vRisk.todo;
  var vDoneRisk = vRisk.done;
  var vTotalRisk = vRisk.total;
  
  var vTechnicalProgress = pProject.technicalprogress;
  var vUnitToRealise = vTechnicalProgress.unittorealise;
  var vUnitRealised = vTechnicalProgress.unitrealised;
  var vUnitLeft = vTechnicalProgress.unitleft;
  var vUnitProgress = vTechnicalProgress.unitprogress;
  
  var vFinancial = pProject.financial;
  
  var vTicket = pProject.ticket;
  var vClosedTicket = vTicket.closed;
  var vTodoTicket = vTicket.todo;
  var vDoneTicket = vTicket.done;
  var vTotalTicket = vTicket.total;
  
  var vRequirement = pProject.requirement;
  var vClosedRequirement = vRequirement.closed;
  var vTodoRequirement = vRequirement.todo;
  var vDoneRequirement = vRequirement.done;
  var vTotalRequirement = vRequirement.total;
  
  var vUserStory = pProject.userstory;
  var vClosedUserStory = vUserStory.closed;
  var vTodoUserStory = vUserStory.todo;
  var vDoneUserStory = vUserStory.done;
  var vTotalUserStory = vUserStory.total;
  
  var vNextMilestone = pProject.nextmilestone;
  var vMilestones = pProject.milestones;
  var vStatus = pProject.status;
  var vManager = pProject.manager;
  var vIdManger = vManager.id;
  var vWeather = pProject.weather;
  var vTrend = pProject.trend;
  var vQuality = pProject.quality;
  var vIdClient = pProject.idclient;
  var vIdOrganization = pProject.idorganization;
  
  this.getId = function() { return vId; };
  this.getID = function() { return "project_"+vId; };  
  this.getName = function() { return vName; };
  this.getColor = function() { return vColor; };
  this.getPriority = function() { return vPriority; };
  this.getPaused = function() { return vPaused; };
  this.getIdle = function() { return vIdle; };
  this.getWbs = function() { return vWbs; };
  this.getHandled = function() { return vHandled; };
  
  this.getValidatedStartDate = function() { return vValidatedStartDate; };
  this.getPlannedStartDate = function() { return vPlannedStartDate; };
  this.getRealStartDate = function() { return vRealStartDate; };
  this.getValidatedEndDate = function() { return vValidatedEndDate; };
  this.getPlannedEndDate = function() { return vPlannedEndDate; };
  this.getRealEndDate = function() { return vRealEndDate; };
  this.getCreationDate = function() { return vCreationDate; };
  this.getTimelineDateValues = function() { return vTimelineDateValues; };
    
  this.getNextMilestone = function() { return vNextMilestone; };
  this.getMilestones = function() { return vMilestones; };
  
  this.getStatusId = function() { return vStatus ? vStatus.id : null; }
  this.getStatus = function() { return vStatus; };
  this.getStatusColor = function() { return vStatusColor; };
  this.getWorkValidated = function() {return vWorkValidated;};
  this.getWorkReal = function() {return vWorkReal;};
  this.getWorkPlanned = function() {return vWorkPlanned;};
  this.getWorkLeft = function() {return vWorkLeft;};
  
  // Color Date
  var vColorValidatedStart = pProject.colorvalidatedstart;
  var vColorPlannedStart = pProject.colorplannedstart;
  var vColorRealStart = pProject.colorrealstart;
  var vColorValidatedEnd = pProject.colorvalidatedend;
  var vColorPlannedEnd = pProject.colorplannedend;
  var vColorRealEnd = pProject.colorrealend;
  
  // Budget
  this.getTotalValidatedCost = function() { return vTotalValidatedCost;};
  this.getTotalRealCost = function() { return vTotalRealCost;};
  this.getTotalPlannedCost = function() { return vTotalPlannedCost;};
  this.getTotalLeftCost = function() { return vTotalLeftCost;};
  
  // Risks
  this.getClosedRisk = function() { return vClosedRisk;};
  this.getTodoRisk = function() { return vTodoRisk;};
  this.getDoneRisk = function() { return vDoneRisk;};
  this.getTotalRisk = function() { return vTotalRisk;};
  
  // Technical Progress
  this.getUnitToRealise = function() { return vUnitToRealise; };
  this.getUnitRealised = function() { return vUnitRealised; };
  this.getUnitLeft = function() { return vUnitLeft; };
  this.getUnitProgress = function () {return vUnitProgress; };
  
  // Financial
  this.getRevenue = function() { return vFinancial.revenue; };
  this.getInvoiced = function() { return vFinancial.invoiced; };
  this.getToBeBilled = function() { return vFinancial.tobebilled; };
  this.getPlannedFinancial = function() { return vFinancial.invoiced + vFinancial.tobebilled; };

  // Tickets
  this.getClosedTicket = function() { return vClosedTicket; };
  this.getDoneTicket = function() { return vDoneTicket; };
  this.getTodoTicket = function() { return vTodoTicket; };
  this.getTotalTicket = function() { return vTotalTicket; };

  // Requirements
  this.getClosedRequirement = function() { return vClosedRequirement; };
  this.getDoneRequirement = function() { return vDoneRequirement; };
  this.getTodoRequirement = function() { return vTodoRequirement; };
  this.getTotalRequirement = function() { return vTotalRequirement; };

  // User Stories
  this.getClosedUserStory = function() { return vClosedUserStory; };
  this.getDoneUserStory = function() { return vDoneUserStory; };
  this.getTodoUserStory = function() { return vTodoUserStory; };
  this.getTotalUserStory = function() { return vTotalUserStory; };
  
  this.getIdManager = function() {return vIdManger;};
  this.getIdClient = function() {return vIdClient;};
  this.getIdOrganization = function() {return vIdOrganization;};
  
  // Draw a tile
  this.drawTile = function() {
    var isLinearView = getDashboardParameter('linearViewDashboard');
    if (isLinearView) {
      return this.drawLinearRow();
    }
    return this.drawTileCard();
  };
  
  this.drawLinearRow = function() {
      var params = getDashboardParameters();
      var listShowMilestone = getMilestoneFilter();
      var minHeight = '70px'; 

      var html = '';
      var globalDisplay = ((!params.showClosedProject && vIdle) || (!params.showPausedProject && vPaused) || (!params.showNotStartedProjects && !vHandled)) ? 'none' : 'flex';  

      html += '<div class="project-row" data-project-id="' + vId + '" data-typeMilestone="' + listShowMilestone + '" ';
      html += 'id="projectRow_' + vId + '" ';
      html += 'style="display:' + globalDisplay + ';align-items:center;border-bottom:1px solid #e0e0e0; padding:8px; gap:12px; min-height:' + minHeight + '; position:relative; overflow:visible; display: flex;">';
      
      // Color name Project
      //html += '<div class="row-project" onclick="top.gotoElement(\'Project\',' + vId + ');" ';
	  html += '<div class="row-project" title="' + i18n('goToDetail') + '" onclick="top.openProjectDetail(' + vId + ');" ';      
	  html += 'style="display:flex;align-items:center;gap:8px;min-width:0;flex:1;cursor:pointer;">';
      html += '<div class="project-color-square" style="background-color:' + vColor + ';"></div>';
      html += '<span class="project-name" title="' + htmlEncode(vName) + '" ';
      html += 'style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block;min-width:0;">';
      html += htmlEncode(vName);
      html += '</span>';
      html += '</div>';
	  
	  
	    // Menu
	    html += '<div class="row-menu-container" style="min-width:40px;display:flex;justify-content: flex-start;position:relative;">';
	    html += '<button class="row-menu-btn" ';
	    html += 'style="background:transparent;border:1px solid #ddd;border-radius:4px;padding:4px;cursor:pointer;position:relative;z-index:1;" ';
	    html += 'onmouseover="this.style.background=\'#f5f5f5\'" onmouseout="this.style.background=\'transparent\'">';
	    html += '<div class="iconOptions16 iconOptions iconSize16 imageColorNewGui"></div>';
	    html += '</button>';

	    // Menu dropdown 
	    html += '<div class="row-menu-dropdown" style="position:absolute;top:100%;right:0;background:white;';
	    html += 'box-shadow:0 4px 12px rgba(0,0,0,0.2);border-radius:4px;opacity:0;visibility:hidden;';
	    html += 'transform:translateY(-10px);transition:all 0.2s;overflow:hidden;z-index:9999;min-width:180px;margin-top:4px;">';
	    
	    // Goto Project
	    html += '<button class="menu-item" title="' + i18n('kanbanGotoItem', new Array(vId, vId)) + '" ';
	    html += 'onclick="event.stopPropagation();top.gotoElement(\'Project\',' + vId + ')" ';
	    html += 'style="display:flex;gap:8px;padding:10px 16px;border:none;background:white;width:100%;cursor:pointer;font-size:13px;text-align:left;" ';
	    html += 'onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	    html += '<div class="iconGoto16 iconGoto iconSize16 imageColorNewGui"></div>';
	    html += '<span>' + i18n('kanbanGotoItem', new Array(vId, vId)) + '</span>';
	    html += '</button>';
	    
	    // Search Planning
	    html += '<button class="menu-item" title="' + i18n('buttonSearch') + '" ';
	    html += 'onclick="event.stopPropagation();top.directSelectProject(\'Project\',' + vId + ',false,true);" ';
	    html += 'style="display:flex;gap:8px;padding:10px 16px;border:none;background:white;width:100%;cursor:pointer;font-size:13px;text-align:left;" ';
	    html += 'onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	    html += '<div class="iconButtonSearchPlanning16 iconButtonSearchPlanning iconSize16 imageColorNewGui"></div>';
	    html += '<span>' + i18n('buttonSearch') + '</span>';
	    html += '</button>';
	    
	    // Goto WorkPlan
	    html += '<button class="menu-item" title="' + i18n('gotoWorkPlan') + '" ';
	    html += 'onclick="event.stopPropagation();setSelectedProject(\'' + vId + '\',\'' + htmlEncode(vName) + '\',\'selectedProject\');gotoElement(\'WorkPlan\',null,false,null,\'workPlan\')" ';
	    html += 'style="display:flex;gap:8px;padding:10px 16px;border:none;background:white;width:100%;cursor:pointer;font-size:13px;text-align:left;" ';
	    html += 'onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	    html += '<div class="iconPlannedWorkManual iconSize16 imageColorNewGui"></div>';
	    html += '<span>' + i18n('gotoWorkPlan') + '</span>';
	    html += '</button>';
	    
	    // Goto Risk
	    html += '<button class="menu-item" title="' + i18n('gotoRisks') + '" ';
	    html += 'onclick="event.stopPropagation();setSelectedProject(\'' + vId + '\',\'' + htmlEncode(vName) + '\',\'selectedProject\');gotoElement(\'Risk\',null,false)" ';
	    html += 'style="display:flex;gap:8px;padding:10px 16px;border:none;background:white;width:100%;cursor:pointer;font-size:13px;text-align:left;" ';
	    html += 'onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	    html += '<div class="iconCriticality16 imageColorNewGui iconCriticality iconSize16"></div>';
	    html += '<span>' + i18n('gotoRisks') + '</span>';
	    html += '</button>';
	    
	    // Download Last attachment
	    if (vLastAtt) {
	      html += '<button class="menu-item" title="' + i18n('downloadLastAttachment') + '" ';
	      html += 'onclick="event.stopPropagation();window.open(\'' + vLastAtt + '\', \'printFrame\')" ';
	      html += 'style="display:flex;gap:8px;padding:10px 16px;border:none;background:white;width:100%;cursor:pointer;font-size:13px;text-align:left;" ';
	      html += 'onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	      html += '<div class="iconButtonDownload16 imageColorNewGui iconButtonDownload iconSize16"></div>';
	      html += '<span>' + i18n('downloadLastAttachment') + '</span>';
	      html += '</button>';
	    }
	    
	    html += '</div>'; // end row-menu-dropdown
	    html += '</div>'; // end row-menu-container
      
      // Manager 
      html += '<div class="row-manager" style="display:flex;align-items:center;width:150px;max-width:150px;min-width:0;flex-shrink:0;position:relative;gap:10px;overflow:hidden;">';
      html += renderManagerHtml(vManager, vId);
      html += '</div>';
      
      // Weather / Trend / Quality
      html += '<div class="row-indicators" style="display:flex;gap:8px;min-width:100px;flex-shrink:0;">';
      html += renderIndicatorHtml(vWeather, vId, 'weather', params.showWeather, true);
      html += renderIndicatorHtml(vTrend, vId, 'trend', params.showTrend, true);
      html += renderIndicatorHtml(vQuality, vId, 'quality', params.showQuality, true);
      html += '</div>';
      
      // Priority
      var priorityDisplay = params.showPriority ? 'flex' : 'none';
      html += '<div class="row-priority" id="priority-' + vId + '" ';
      html += 'data-priority-value="' + htmlEncode(vPriority) + '" ';
      html += 'data-priority-label="' + htmlEncode(i18n('Priority')) + '" ';
      html += 'style="display:' + priorityDisplay + ';min-width:80px;align-items:center;justify-content:center;">';
      if (vPriority) {
          html += '<div style="display:flex;align-items:center;gap:4px;padding:4px 8px;background:#E8E8E8;border-radius:4px;">';
          html += '<div class="iconPriorityColor iconSize22"></div>';
          html += '<span style="font-size:12px;">' + htmlEncode(vPriority) + '</span>';
          html += '</div>';
      } else {
          html += '-';
      }
      html += '</div>';
      
	  // Status
	  var statusDisplay = params.showStatus ? 'flex' : 'none';
	  html += '<div class="row-status" style="display:' + statusDisplay + ';min-width:110px;flex-shrink:0;align-items:center;justify-content:center;">'; 
	  if (vStatus && vStatus.name) {
	      html += '<div style="padding:4px 12px;border-radius:12px;background-color:' + vStatus.color + ';';
	      html += 'color:' + getForeColor(vStatus.color) + ';font-size:12px;white-space:nowrap;display:inline-block;">';
	      html += vStatus.name;
	      html += '</div>';
	  }
	  html += '</div>';
      
      // Next Milestone
      var milestoneDisplay = params.showNextMilestone ? 'flex' : 'none';
      html += '<div class="row-milestone" style="display:' + milestoneDisplay + ';min-width:40px;justify-content:center;">';
      html += renderNextMilestoneHtml(vMilestones, listShowMilestone, vId, milestoneDisplay, colorMilestone);
      html += '</div>';
      
      // Dates 
      html += '<div class="row-dates" style="display:flex;flex-direction:column;gap:4px;min-width:120px;">';    
      var startDisplay = params.showDatesStart ? 'block' : 'none';
      var endDisplay = params.showDatesEnd ? 'block' : 'none';     
      // Start Dates
      html += renderDatesRows([
          { value: vValidatedStartDate, label: i18n('colValidatedStartDate'), color: vColorValidatedStart },
          { value: vPlannedStartDate,   label: i18n('colPlannedStartDate'),   color: vColorPlannedStart },
          { value: vRealStartDate,      label: i18n('colRealStartDate'),      color: vColorRealStart }
      ], 'start', startDisplay, vId);

      // End Dates
      html += renderDatesRows([
          { value: vValidatedEndDate, label: i18n('colValidatedEndDate'), color: vColorValidatedEnd },
          { value: vPlannedEndDate,   label: i18n('colPlannedEndDate'),   color: vColorPlannedEnd },
          { value: vRealEndDate,      label: i18n('colRealEndDate'),      color: vColorRealEnd }
      ], 'end', endDisplay, vId);
      html += '</div>';
      
	  html += '<div class="row-progress-timeline-wrapper" style="display:flex;gap:15px;flex:2;min-width:0;align-items:center;">';
      // Progress Charts
	  html += '<div class="row-progress" style="position:relative;display:flex;gap:15px;flex-shrink:0;align-items:center;">';
      html += '<div class="tile-work-progress" style="width:80px;height:80px;position:relative;' + (params.showWorkProgress ? '' : 'display:none;') + '"><canvas id="workProgress-' + vId + '" width="80" height="80"></canvas></div>';
      html += '<div class="tile-budget-progress" style="width:80px;height:80px;position:relative;' + (params.showBudgetProgress ? '' : 'display:none;') + '"><canvas id="budgetProgress-' + vId + '" width="80" height="80"></canvas></div>';
      html += '<div class="tile-risks-progress" style="width:80px;height:80px;position:relative;' + (params.showRisksProgress ? '' : 'display:none;') + '"><canvas id="risksProgress-' + vId + '" width="80" height="80"></canvas></div>';
      html += '<div class="tile-technical-progress" style="width:80px;height:80px;position:relative;' + (params.showTechnicalProgress ? '' : 'display:none;') + '"><canvas id="technicalProgress-' + vId + '" width="80" height="80"></canvas></div>';
      html += '<div class="tile-financial-progress" style="width:80px;height:80px;position:relative;' + (params.showFinancialProgress ? '' : 'display:none;') + '"><canvas id="financialProgress-' + vId + '" width="80" height="80"></canvas></div>';
      html += '<div class="tile-tickets-progress" style="width:80px;height:80px;position:relative;' + (params.showTicketsProgress ? '' : 'display:none;') + '"><canvas id="ticketsProgress-' + vId + '" width="80" height="80"></canvas></div>';
      html += '<div class="tile-requirements-progress" style="width:80px;height:80px;position:relative;' + (params.showRequirementsProgress ? '' : 'display:none;') + '"><canvas id="requirementsProgress-' + vId + '" width="80" height="80"></canvas></div>';
      html += '<div class="tile-userstories-progress" style="width:80px;height:80px;position:relative;' + (params.showUserStoriesProgress ? '' : 'display:none;') + '"><canvas id="userStoriesProgress-' + vId + '" width="80" height="80"></canvas></div>';
      html += '</div>';
	  // Timeline
	  var timelineDisplay = params.showTimeline ? 'flex' : 'none';
	  html += '<div class="row-timeline" style="display:' + timelineDisplay + ';flex:1;min-width:0;align-items:center;">';
	  html += '<canvas id="timeline-' + vId + '" style="width:100%;height:60px;"></canvas>';
	  html += '</div>';
	  
	  html += '</div>';
	  
	  html += '</div>'; // end project-row
	  
	  return html;
	};
  
  this.drawTileCard = function() {
	var params = getDashboardParameters();
	var listShowMilestone = getMilestoneFilter();
    var html = '';
    
	var globalDisplay = ((!params.showClosedProject && vIdle) || (!params.showPausedProject && vPaused) || (!params.showNotStartedProjects && !vHandled)) ? 'none' : 'block';
	html += '<div class="project-tile" data-project-id="' + vId + '" data-project-color="' + vColor + '" data-typeMilestone ="'+listShowMilestone+'" id="project_'+vId+'" style="display:' + globalDisplay + ';">';
    
    // ========== UPPER PART: DATES ==========
	var backgroundStyle = '';
	if (vFile) backgroundStyle = 'url(&quot;' + vFile + '&quot;) center/cover no-repeat';
	else backgroundStyle = vColor ? 'linear-gradient(135deg, ' + vColor + ' 0%, #e9ecef 100%)' : 'linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)';

	//html += '<div class="tile-dates-section" onclick="if(event.target === this) {top.gotoElement(\'Project\',' + vId + ');}" style="cursor:pointer;background: ' + backgroundStyle + ';">';
	html += '<div class="tile-dates-section" title="' + i18n('goToDetail') + '" onclick="if(event.target === this) {top.openProjectDetail(' + vId + ');}" style="cursor:pointer;background: ' + backgroundStyle + ';">';
	
	// Button menu
	html += '<div class="tile-menu-container" style="position:absolute;top:8px;right:8px;z-index:1000;">';
	html += '  <button class="tile-menu-btn" style="background:rgba(255,255,255,0.3);border-radius:6px;padding:6px;border:none;cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background=\'rgba(255,255,255,0.4)\'" onmouseout="this.style.background=\'rgba(255,255,255,0.2)\'">';
	html += '      <div class="iconOptions16 iconOptions iconSize16 imageColorNewGui"></div>';
	html += '  </button>';
	html += '  <div class="tile-menu-dropdown" style="position:absolute;top:36px;right:0;background:white;opacity:0;visibility:hidden;transform:translateY(-10px);transition:all 0.2s;overflow:hidden;">';

	// Goto Project
	html += '    <button class="menu-item" title="'+i18n('kanbanGotoItem',new Array(vId, vId))+'" onclick="event.stopPropagation();top.gotoElement(\'Project\','+vId+')" onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	html += '      <div class="iconGoto16 iconGoto iconSize16 imageColorNewGui"></div>';
	html += '    </button>';

	// Search Planning
	html += '    <button class="menu-item" title="'+i18n('buttonSearch')+'" onclick="event.stopPropagation();top.directSelectProject(\'Project\','+vId+',false,true);" onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	html += '      <div class="iconButtonSearchPlanning16 iconButtonSearchPlanning iconSize16 imageColorNewGui"></div>';
	html += '    </button>';

	// Goto WorkPlan
	html += '    <button class="menu-item" title="'+i18n('gotoWorkPlan')+'" onclick="event.stopPropagation();setSelectedProject(\''+vId+'\',\''+htmlEncode(vName)+'\',\'selectedProject\');gotoElement(\'WorkPlan\',null,false,null,\'workPlan\')" onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	html += '      <div class="iconPlannedWorkManual iconSize16 imageColorNewGui"></div>';
	html += '    </button>';

	// Goto Risk
	html += '    <button class="menu-item" title="'+i18n('gotoRisks')+'" onclick="event.stopPropagation();setSelectedProject(\''+vId+'\',\''+htmlEncode(vName)+'\',\'selectedProject\');gotoElement(\'Risk\',null,false)" onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	html += '      <div class="iconCriticality16 imageColorNewGui iconCriticality iconSize16"></div>';
	html += '    </button>';

	//DownLoad Last attachment
	if (vLastAtt){
	    html += '    <button class="menu-item" title="'+i18n('downloadLastAttachment')+'" onclick="event.stopPropagation();window.open(\''+vLastAtt+'\', \'printFrame\')" onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'white\'">';
	    html += '      <div class="iconButtonDownload16 imageColorNewGui iconButtonDownload iconSize16"></div>';
	    html += '    </button>';
	}
	
	html += '  </div>';
	html += '</div>';
	
	if (vFile){
	  html += '<div id="addAttachementProjectPic_'+vId+'" class="project-photo-btn" data-photo-id="'+vIdPhoto+'" data-project-id="'+vId+'" title="'+i18n('removeAttachementProjectPic')+'" onclick="event.stopPropagation(); removeAttachmentWithConfirm(this, '+vIdPhoto+', '+vId+');" style="position:absolute;top:50%;left:50%;transform:translate(-50%, -50%);transition:all 0.3s;background:rgba(255,255,255,0.9);border-radius:50%;padding:12px;box-shadow:0 2px 8px rgba(0,0,0,0.15);cursor:pointer;" onmouseover="this.style.background=\'white\';this.style.boxShadow=\'0 4px 12px rgba(0,0,0,0.25)\'" onmouseout="this.style.background=\'rgba(255,255,255,0.9)\';this.style.boxShadow=\'0 2px 8px rgba(0,0,0,0.15)\'">'; 
	  html += '  <div class="iconRemove16 imageColorNewGui iconRemove iconSize16"></div></div>';
	}else {
	  html += '<div id="addAttachementProjectPic_'+vId+'" class="project-photo-btn" data-project-id="'+vId+'" title="'+i18n('addAttachementProjectPic')+'" onclick="event.stopPropagation(); addAttachmentWithUpdate(this,\'Project\','+vId+',\'profilePic\');" style="position:absolute;top:50%;left:50%;transform:translate(-50%, -50%);transition:all 0.3s;background:rgba(255,255,255,0.9);border-radius:50%;padding:12px;box-shadow:0 2px 8px rgba(0,0,0,0.15);cursor:pointer;" onmouseover="this.style.background=\'white\';this.style.boxShadow=\'0 4px 12px rgba(0,0,0,0.25)\'" onmouseout="this.style.background=\'rgba(255,255,255,0.9)\';this.style.boxShadow=\'0 2px 8px rgba(0,0,0,0.15)\'">';
	  html += '  <div class="iconAdd16 imageColorNewGui iconAdd iconSize16"></div></div>';
	}
	
	var startDisplay = params.showDatesStart ? 'block' : 'none';
	var endDisplay = params.showDatesEnd ? 'block' : 'none';

	// Start Dates
	html += renderDatesRows([
	  { value: vValidatedStartDate, label: i18n('colValidatedStartDate'), color: vColorValidatedStart },
	  { value: vPlannedStartDate,   label: i18n('colPlannedStartDate'),   color: vColorPlannedStart },
	  { value: vRealStartDate,      label: i18n('colRealStartDate'),      color: vColorRealStart }
	], 'start', startDisplay, vId);

	// End Dates
	html += renderDatesRows([
	  { value: vValidatedEndDate, label: i18n('colValidatedEndDate'), color: vColorValidatedEnd },
	  { value: vPlannedEndDate,   label: i18n('colPlannedEndDate'),   color: vColorPlannedEnd },
	  { value: vRealEndDate,      label: i18n('colRealEndDate'),      color: vColorRealEnd }
	], 'end', endDisplay, vId);


	html += '</div>';
    
    // ========== MAIN PART ==========
    html += '<div class="tile-main">';
    
	html += '<div style="display:flex; flex-direction: row-reverse; gap:10px; position:absolute; top:-12px; right:10px; z-index:10;">';
	// Status
	var statusDisplay = params.showStatus ? 'flex' : 'none';
	if (vStatus.name) {
	  html += '<div class="project-status" style="display:' + statusDisplay + ';background-color: ' + vStatus.color + ';color:'+getForeColor(vStatus.color)+'">';
	  html += vStatus.name;
	  html += '</div>';
	}

	var priorityDisplay = params.showPriority ? 'flex' : 'none';
	if (vPriority) {
	  html += '<div class="tile-priority" style="display:' + priorityDisplay + ';gap:4px;background:#E8E8E8;color:var(--color-dark);"';
	  html += 'id="priority-' + vId + '" ';
	  html += 'data-priority-value="' + htmlEncode(vPriority) + '" ';
	  html += 'data-priority-label="' + htmlEncode(i18n('Priority')) + '" >';
	  html += '<div class="iconPriority16 iconPriority iconSize16 imageColorNewGuiNoSelection"></div>';
	  html += '<span>' + htmlEncode(vPriority) + '</span>';
	  html += '</div>';
	}
	html += '</div>';
    
	html += '<div class="tile-header" style="display:flex;align-items:center;justify-content:space-between;	min-height: 36px;">';

	// Left part :square + name
	html += '<div class="tile-header-left" style="display:flex;align-items:center;gap:6px;cursor: pointer;" onclick="top.gotoElement(\'Project\','+vId+');">';
	html += '  <div class="project-color-square" style="background-color:' + vColor + '"></div>';
	html += '  <h3 class="project-title" style="font-size:14px;font-weight:600;">' + vName + '</h3>';
	html += '</div>';

	// Right part : Next Milestone
	html += '<div class="tile-header-right" style="display:flex;align-items:center;">';

	var milestoneDisplay = params.showNextMilestone ? 'flex' : 'none';
	if (vNextMilestone) {
	  var nextMilestoneData = getNextMilestoneFiltered(vMilestones, listShowMilestone);  
	  if (nextMilestoneData) {
	    var milestone = nextMilestoneData.date;
	    var milestoneName = nextMilestoneData.name;
	    
	    let useCustomColor = false;
	    let customColor = '#ffa64d';	  
	    if (colorMilestone && nextMilestoneData.color) {
	      useCustomColor = true;
	      customColor = nextMilestoneData.color;
	    }	  
	    let validationColor = '#44af69';
	    let hasValidated = nextMilestoneData.validateddate !== null && nextMilestoneData.validateddate !== undefined;
	    let hasPlanned = nextMilestoneData.planneddate !== null && nextMilestoneData.planneddate !== undefined;
	    if (hasValidated && hasPlanned && nextMilestoneData.plannedDateParsed > nextMilestoneData.validatedDateParsed) {
	      validationColor = '#f8333c';
	    }	  

	    const milestoneColor = useCustomColor ? customColor : validationColor;
	    var darkerMilestoneColor = darkenColor(milestoneColor, 20);

	    var parts = milestone.split('/');
	    var day = parts[0]?.padStart(2, '0') || '--';
	    var month = parts[1]?.padStart(2, '0') || '--';

	    html += '<div class="tile-next-milestone" ';
	    html += 'id="milestone-' + vId + '" ';
	    html += 'data-milestone-name="' + htmlEncode(milestoneName) + '" ';
	    html += 'data-milestone-date="' + htmlEncode(milestone) + '" ';
	    html += 'data-milestone-label="' + htmlEncode(i18n('nextMilestoneDashboard')) + '" ';
		html += 'style="display:' + milestoneDisplay +';background-color:' + milestoneColor +';border:2px solid ' + darkerMilestoneColor +';color:' + getForeColor(milestoneColor) +';width:28px;height:28px;' +
		        'font-size:11px;' +'line-height:1;' +'border-radius:50%;' +'display:flex;flex-direction:column;' +'align-items:center;justify-content:center;">';
	    html += '  <div style="line-height:1;">' + day + '</div>';
	    html += '  <div style="line-height:1;">' + month + '</div>';
	    html += '</div>';
	  }
	}

	html += '</div>'; // End tile-header-right
	html += '</div>'; // End tile-header
	
	html += '<div class="tile-manager" style="display:flex;align-items:center;justify-content:space-between;min-width:0;">';

	/* ================= LEFT : MANAGER ================= */
	html += '<div class="tile-manager-left" style="display:flex;align-items:center;gap:6px;margin-top:6px;min-width:0;overflow:hidden;flex:1;">';
	html += renderManagerHtml(vManager, vId);
	html += '</div>';

	/* ================= RIGHT : WEATHER / TREND / QUALITY ================= */
	html += '<div class="tile-manager-right" style="display:flex;align-items:center;gap:8px;margin-top:6px;flex-shrink:0;">';

	html += renderIndicatorHtml(vWeather, vId, 'weather', params.showWeather,false);
	html += renderIndicatorHtml(vTrend, vId, 'trend', params.showTrend,false);
	html += renderIndicatorHtml(vQuality, vId, 'quality', params.showQuality,false);

	html += '</div>'; // manager-right
	html += '</div>'; // tile-manager
		
	// Timeline
	var timelineDisplay = params.showTimeline ? 'block' : 'none';
	html += '<div class="tile-timeline" style="display:' + timelineDisplay + ';">';
	html += '<canvas id="timeline-' + vId + '"></canvas>';
	html += '</div>';
	
	
	// =================== Progress charts ===================
	html += `<div class="tile-progress-charts">`;
	var fullRight ='';
	var fullLeft = '';
//	if (dojo.byId('hideStreamNewGui') && dojo.byId('hideStreamNewGui').style.display === "none" && showWorkProgress && showBudgetProgress &&  showRisksProgress){
//		fullRight = 'right:-10px;';
//		fullLeft = 'left:-10px;';
//	}
	
	// Work progress
	var progressDisplay = params.showWorkProgress ? 'block' : 'none';
	html += '<div class="tile-work-progress" style="display:' + progressDisplay + ';'+fullRight+'">';
	html += '<canvas id="workProgress-' + vId + '"></canvas>';
	html += '</div>';
	
	// Budget progress
	var budgetProgressDisplay = params.showBudgetProgress ? 'block' : 'none';
	html += '<div class="tile-budget-progress" style="display:' + budgetProgressDisplay + ';">';
	html += '<canvas id="budgetProgress-' + vId + '"></canvas>';
	html += '</div>';
	
	// Risks progress
	var risksProgressDisplay = params.showRisksProgress ? 'block' : 'none';
	html += '<div class="tile-risks-progress" style="display:' + risksProgressDisplay + ';'+fullLeft+'">';
	html += '<canvas id="risksProgress-' + vId + '"></canvas>';
	html += '</div>';
	
	// Technical progress
	var technicalProgressDisplay = params.showTechnicalProgress ? 'block' : 'none';
	html += '<div class="tile-technical-progress" style="display:' + technicalProgressDisplay + ';'+fullLeft+'">';
	html += '<canvas id="technicalProgress-' + vId + '"></canvas>';
	html += '</div>';
	
	// Financial progress
	var financialProgressDisplay = params.showFinancialProgress ? 'block' : 'none';
	html += '<div class="tile-financial-progress" style="display:' + financialProgressDisplay + ';'+fullLeft+'">';
	html += '<canvas id="financialProgress-' + vId + '"></canvas>';
	html += '</div>';
	
	// Tickets progress
	var ticketsProgressDisplay = params.showTicketsProgress ? 'block' : 'none';
	html += '<div class="tile-tickets-progress" style="display:' + ticketsProgressDisplay + ';'+fullLeft+'">';
	html += '<canvas id="ticketsProgress-' + vId + '"></canvas>';
	html += '</div>';
	
	// Requirements progress
	var requirementsProgressDisplay = params.showRequirementsProgress ? 'block' : 'none';
	html += '<div class="tile-requirements-progress" style="display:' + requirementsProgressDisplay + ';'+fullLeft+'">';
	html += '<canvas id="requirementsProgress-' + vId + '"></canvas>';
	html += '</div>';
	
	// User Stories progress
	var userStoriesProgressDisplay = params.showUserStoriesProgress ? 'block' : 'none';
	html += '<div class="tile-userstories-progress" style="display:' + userStoriesProgressDisplay + ';'+fullLeft+'">';
	html += '<canvas id="userStoriesProgress-' + vId + '"></canvas>';
	html += '</div>';
	
	html += '</div>'; //End progress charts
	
    html += '</div>'; // end tile-main
    
	
	// ============= BOTTOM PART: SHORTCUTS =============
    html += '</div>'; // end project-tile
    
    return html;
  };
};

// ==================== MAIN FUNCTION : DRAW DASHBOARD ====================
function drawProjectDashboard(onlyRefresh) {
  if (onlyRefresh === undefined) onlyRefresh = false;
  
  // Create obj Dashboard
  if (!onlyRefresh) {
	initializeProgressChartHistory(); 
    window.dbd = new JSDashboard.Dashboard();
  }
  
  // JSON
  var jsonData = getJsonDashboardData();
  
  // Check data
  if (!jsonData || jsonData.innerHTML.indexOf('{"identifier"') < 0) {
    if (jsonData) {
      showAlert(jsonData.innerHTML);
    }
    hideWait();
    return;
  }
  // Parse the JSON
  try {
    var store = eval('(' + jsonData.innerHTML + ')');
  } catch(e) {
    console.error('ERROR Parsing jsonData in drawProjectDashboard()');
    console.error(jsonData.innerHTML);
    hideWait();
    return;
  }
  var projects = store.items;
  dbd.clearProjects();
  // Create obj Project
  for (var i = 0; i < projects.length; i++) {
    var projectData = projects[i];
    var newProject = new JSDashboard.Project(projectData);
    dbd.AddProject(newProject);
  }
  dbd.Draw();
  initMilestoneFilterListener();
}

function renderDatesRows(datesArray, type, displayValue, projectId) {
  var html = '';
  var isLinearView = getDashboardParameter('linearViewDashboard');
  
  datesArray.forEach(function(dateInfo, index) {
    var isEmpty = !dateInfo.value || dateInfo.value === '—';
    if (!isLinearView) var dateId = type + 'Date_' + projectId + '_' + index;
	else var dateId  = 'linear' + type + 'Date_' + projectId + '_' + index;

    var displayText = isEmpty ? i18n('undefinedValue') : dateInfo.value;
    var displayTextShort = isEmpty ? '-' : dateInfo.value;

    var backgroundColor = '';
    var textColor = '';
	var borderStyle = '';

    if (!isEmpty && dateInfo.color) {
      if (dateInfo.color.indexOf('gradient') !== -1) {
        backgroundColor = 'background:' + dateInfo.color + ';';
      } else {
        backgroundColor = 'background-color:' + dateInfo.color + ';';
      }
      textColor = 'color:' + getForeColor(dateInfo.color) + ';';
    }

    if (isLinearView && isEmpty) {
      backgroundColor = 'background-color:#f0f0f0;';
      textColor = 'color:#ccc;';
    }
	if ((backgroundColor == 'background-color:#FFFFFF;' || !backgroundColor) && isLinearView)  borderStyle = 'border: 1px solid #ccc;';
    html += '<div class="date-row date-' + type + (isEmpty ? ' no-date' : '') + '" ';
    html += 'id="' + dateId + '" ';
    html += 'data-date-label="' + htmlEncode(dateInfo.label) + '" ';
    html += 'data-date-value="' + htmlEncode(displayText) + '" ';
    html += 'style="display:' + displayValue + ';' + backgroundColor + textColor + borderStyle +'">';

    html += displayTextShort;

    html += '</div>';
  });

  return html;
}


function renderNextMilestoneHtml(vMilestones, listShowMilestone, vId, milestoneDisplay, colorMilestone) {
  var vNextMilestone = getNextMilestoneFiltered(vMilestones, listShowMilestone); 
  var html = '';
  if (!vNextMilestone) return '';
  
  var nextMilestoneData = getNextMilestoneFiltered(vMilestones, listShowMilestone);
  if (!nextMilestoneData) return '';
  
  var milestone = nextMilestoneData.date;
  var milestoneName = nextMilestoneData.name;
  
  let useCustomColor = false;
  let customColor = '#ffa64d';
  if (colorMilestone && nextMilestoneData.color) {
    useCustomColor = true;
    customColor = nextMilestoneData.color;
  }
  
  let validationColor = '#44af69';
  let hasValidated = nextMilestoneData.validateddate != null;
  let hasPlanned = nextMilestoneData.planneddate != null;
  if (hasValidated && hasPlanned && nextMilestoneData.plannedDateParsed > nextMilestoneData.validatedDateParsed) {
    validationColor = '#f8333c';
  }
  
  const milestoneColor = useCustomColor ? customColor : validationColor;
  var darkerMilestoneColor = darkenColor(milestoneColor, 20);
  
  var parts = milestone ? milestone.split('/') : [];
  var day = parts[0] ? parts[0].padStart(2, '0') : '--';
  var month = parts[1] ? parts[1].padStart(2, '0') : '--';
  
  html += '<div class="tile-next-milestone" id="milestone-' + vId + '" ';
  html += 'data-milestone-name="' + htmlEncode(milestoneName) + '" ';
  html += 'data-milestone-date="' + htmlEncode(milestone) + '" ';
  html += 'data-milestone-label="' + htmlEncode(i18n('nextMilestoneDashboard')) + '" ';
  html += 'style="display:' + milestoneDisplay + ';background-color:' + milestoneColor + ';';
  html += 'border:2px solid ' + darkerMilestoneColor + ';color:' + getForeColor(milestoneColor) + ';';
  html += 'width:28px;height:28px;font-size:11px;line-height:1;border-radius:50%;';
  html += 'display:flex;flex-direction:column;align-items:center;justify-content:center;">';
  html += '<div style="line-height:1;">' + day + '</div>';
  html += '<div style="line-height:1;">' + month + '</div>';
  html += '</div>';
  
  return html;
}

function renderManagerHtml(vManager, vId) {
  var html = '';
  
  var hasManager = vManager && vManager.name;
  	if (hasManager){
  	  if (vManager.isfile) {
  		html += '<img id="responsible' + vId + '" valueuser="' + htmlDecode(vManager.name) + '" ';
  		html += 'style="border-radius:5px;float:left;height:32px;min-width:32px;top:1px;" ';
  		html += 'src="' + htmlDecode(vManager.file) + '" ';
  		html += 'onmouseenter="showToolTip(\'tooltipUserThumb_' + vId + '\');" ';
  		html += 'onmouseleave="hideToolTip(\'tooltipUserThumb_' + vId + '\', 200);" />';
  	  } else {
  		var arrayColors = ['#1abc9c', '#2ecc71', '#3498db', '#9b59b6', '#34495e','#16a085', '#27ae60', '#2980b9', '#8e44ad', '#2c3e50','#f1c40f', '#e67e22', '#99CC00', '#e74c3c', '#95a5a6','#d35400', '#c0392b', '#bdc3c7', '#7f8c8d'];
  		var keyColor = vManager.id % arrayColors.length;
  		var bgColor = (keyColor in arrayColors) ? arrayColors[keyColor] : arrayColors[0];
  		html += '<span style="color:#ffffff;background-color:' + bgColor + ';float:left;font-size:24px;border-radius:5px;font-weight:300;text-shadow:none;text-align:center;height:32px;min-width:32px;top:1px;" ';
  		html += 'onmouseenter="showToolTip(\'tooltipUserThumb_' + vId + '\');" ';
  		html += 'onmouseleave="hideToolTip(\'tooltipUserThumb_' + vId + '\', 200);" ';
  		html += 'id="responsible' + vId + '" valueuser="' + htmlDecode(vManager.name) + '">' + htmlDecode(vManager.file) + '</span>';
  	  }
  	  html += '<span class="manager-name" style="font-size:13px;color:#333;position:relative;top:0px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;" ';
  	  html += 'onmouseenter="showToolTip(\'tooltipUserThumb_' + vId + '\');" ';
  	  html += 'onmouseleave="hideToolTip(\'tooltipUserThumb_' + vId + '\', 200);">';
  	  html += htmlDecode(vManager.namemanager) + '</span>';
  	  // Tooltip manager
  	  html += '<div class="comboButtonInvisible" dojoType="dijit.form.DropDownButton" id="tooltipUserThumb_' + vId + '" ';
  	  html += 'name="tooltipUserThumb_' + vId + '" style="position:absolute;top:' + (20 * 0.75) + 'px;left:-' + (20 * 0.25) + 'px;height:0px;overflow:hidden;">';
  	  html += '  <div dojoType="dijit.TooltipDialog" id="dialogTooltipUserThumb_' + vId + '" style="cursor:pointer;" ';
  	  html += 'onMouseEnter="clearTimeout(hideToolTipTimeout);" onMouseLeave="hideToolTip(\'tooltipUserThumb_' + vId + '\',200);" >';
  	  html += '    <table style="width:100%"><tr>';
  	  html += '      <td style="padding-right:5px;">';
  	  html += (vManager.isfile) ? '<img style="border:1px solid #AAA;width:32px;height:32px;float:left;" src="' + htmlDecode(vManager.file) + '"/>' : '';
  	  html += '      </td>';
  	  html += '      <td style="min-width:100px;max-width:200px;">' + htmlDecode(vManager.name) + '</td>';
  	  html += '    </tr></table>';
  	  html += '  </div>';
  	  html += '</div>';
  	} else {
  	  // No manager - display placeholder
	  html += '<span class="manager-name" id="managerName' + vId + '" ';
	  html += 'data-manager-undefined="true" ';
	  html += 'style="font-size:13px;color:#cccccc;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;">';
  	  html += '-</span>';
  	  html += '<span class="manager-name" id="managerName' + vId + '" ';
  	  html += 'data-manager-undefined="true" ';
  	  html += 'style="font-size:13px;color:#cccccc;cursor:pointer;">';
  	  html += i18n('undefinedValue') + '</span>';	
  	}
  
  return html;
}

function renderIndicatorHtml(indicator, vId, type, show, isLinearView) {
  if (!indicator) indicator = {};

  var display = show ? 'flex' : 'none';
  var name = indicator.name ? htmlEncode(indicator.name) : '';
  var color = indicator.color || '#ccc';
  var icon = indicator.icon || null;
  var className = isLinearView ? 'row-' + type : 'tile-indicator tile-' + type;
  var idType = isLinearView ?  type + 'Linear-' + vId  : type + '-' + vId ;

  var html = '';
  html += '<div class="' + className + '" id="'+idType+'" ';
  html += 'data-' + type + '-name="' + name + '" ';
  html += 'style="display:' + display + ';align-items:center;justify-content:center;width:36px;height:24px;">';

  if (icon) {
    html += '<img style="width:32px;height:32px;" src="icons/' + icon + '"/>';
  } else {
    html += '<div style="width:32px;height:32px;border-radius:50%;background:' + color + ';"></div>';
  }

  html += '</div>';
  return html;
}



function setupTooltipsForProject(project, isLinearView) {
  var prefix = isLinearView ? 'Linear' : '';
  
  // Weather tooltip
  var weatherElement = document.getElementById('weather' + prefix + '-' + project.getId());
  if (weatherElement) {
    setupTooltipDashboard(weatherElement, function() {
      var label = this.getAttribute('data-weather-name');
      var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
      return labelBis;
    }.bind(weatherElement));
  }
  
  // Trend tooltip
  var trendElement = document.getElementById('trend' + prefix + '-' + project.getId());
  if (trendElement) {
    setupTooltipDashboard(trendElement, function() {
      var label = this.getAttribute('data-trend-name');
      var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
      return labelBis;
    }.bind(trendElement));
  }
  
  // Quality tooltip
  var qualityElement = document.getElementById('quality' + prefix + '-' + project.getId());
  if (qualityElement) {
    setupTooltipDashboard(qualityElement, function() {
      var label = this.getAttribute('data-quality-name');
      var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
      return labelBis;
    }.bind(qualityElement));
  }
  
  // Date tooltips - Start dates
  for (var j = 0; j < 3; j++) {
    var startDateElement = document.getElementById((isLinearView ? 'linearstart' : 'start') + 'Date_' + project.getId() + '_' + j);
    if (startDateElement) {
      setupTooltipDashboard(startDateElement, function() {
        var label = this.getAttribute('data-date-label');
        var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
        var value = this.getAttribute('data-date-value');
        return labelBis + ' : ' + value;
      }.bind(startDateElement));
    }
  }
  
  // Date tooltips - End dates
  for (var j = 0; j < 3; j++) {
    var endDateElement = document.getElementById((isLinearView ? 'linearend' : 'end') + 'Date_' + project.getId() + '_' + j);
    if (endDateElement) {
      setupTooltipDashboard(endDateElement, function() {
        var label = this.getAttribute('data-date-label');
        var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
        var value = this.getAttribute('data-date-value');
        return labelBis + ' : ' + value;
      }.bind(endDateElement));
    }
  }
  
  // Milestone tooltip
  var milestoneElement = document.getElementById('milestone-' + project.getId());
  if (milestoneElement) {
    setupTooltipDashboard(milestoneElement, function() {
      var label = this.getAttribute('data-milestone-label');
      var date = this.getAttribute('data-milestone-date');
      var name = this.getAttribute('data-milestone-name');
      return { toString: function() { return label + ' : ' + date + '<br>' + name; } };
    }.bind(milestoneElement));
  }
  
  // Priority tooltip
  var priorityElement = document.getElementById('priority-' + project.getId());
  if (priorityElement) {
    setupTooltipDashboard(priorityElement, function() {
      var label = this.getAttribute('data-priority-label');
      var value = this.getAttribute('data-priority-value');
      return label + ' : ' + value;
    }.bind(priorityElement));
  }
  
  // No manager defined
  var managerNameElement = document.getElementById('managerName' + project.getId());
  if (managerNameElement) {
    var isUndefined = managerNameElement.getAttribute('data-manager-undefined') === 'true';
    if (isUndefined) {
      setupTooltipDashboard(managerNameElement, function() {
        return i18n('Responsible') + ' : ' + i18n('undefinedValue');
      });
    }
  }
}

function getTimelineDateValues(projectData) {
  projectData = projectData || {};
  return {
    validatedStartDate: projectData.validatedstartdateiso,
    plannedStartDate: projectData.plannedstartdateiso,
    realStartDate: projectData.realstartdateiso,
    validatedEndDate: projectData.validatedenddateiso,
    plannedEndDate: projectData.plannedenddateiso,
    realEndDate: projectData.realenddateiso,
    creationDate: projectData.creationdateiso
  };
}

function formatProjectDashboardDate(isoDate, formattedDate) {
  if (!isoDate || !currentLocale) return formattedDate;

  const date = parseDate(isoDate);
  if (!date) return formattedDate;

  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const locale = currentLocale.toLowerCase().substring(0, 2);
  if (locale === 'fr') return day + '/' + month + '/' + date.getFullYear();
  if (locale === 'en') return month + '/' + day + '/' + date.getFullYear();
  return formattedDate;
}

function formatProjectDashboardDisplayDates(projectData) {
  if (!projectData) return;

  projectData.validatedstartdate = formatProjectDashboardDate(projectData.validatedstartdateiso, projectData.validatedstartdate);
  projectData.plannedstartdate = formatProjectDashboardDate(projectData.plannedstartdateiso, projectData.plannedstartdate);
  projectData.realstartdate = formatProjectDashboardDate(projectData.realstartdateiso, projectData.realstartdate);
  projectData.validatedenddate = formatProjectDashboardDate(projectData.validatedenddateiso, projectData.validatedenddate);
  projectData.plannedenddate = formatProjectDashboardDate(projectData.plannedenddateiso, projectData.plannedenddate);
  projectData.realenddate = formatProjectDashboardDate(projectData.realenddateiso, projectData.realenddate);
  projectData.creationdate = formatProjectDashboardDate(projectData.creationdateiso, projectData.creationdate);

  if (Array.isArray(projectData.milestones)) {
    projectData.milestones.forEach(function(milestone) {
      milestone.validateddate = formatProjectDashboardDate(milestone.validateddateiso, milestone.validateddate);
      milestone.plannedenddate = formatProjectDashboardDate(milestone.plannedenddateiso, milestone.plannedenddate);
      milestone.realenddate = formatProjectDashboardDate(milestone.realenddateiso, milestone.realenddate);
      var milestoneDateIso = milestone.validateddateiso || milestone.plannedenddateiso || milestone.realenddateiso;
      milestone.date = formatProjectDashboardDate(milestoneDateIso, milestone.date);
    });
  }
}

// ==================== TIMELINE FUNCTION ====================
function createTimeline(canvasId,validatedStartDate,plannedStartDate,realStartDate,validatedEndDate,plannedEndDate,realEndDate,milestones,useColor,dateValues) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  let interactiveElements = [];
  
  function drawTimeline() {
    const projectTile = canvas.closest('.project-tile');
    const projectRow = canvas.closest('.project-row');
    const isLinearView = projectRow !== null;
	const detailBlock = canvas.closest('.detail-milestone-block');
	
    let width, height;
    
    if (isLinearView) {
      const timelineContainer = canvas.parentElement;
      width = timelineContainer ? timelineContainer.clientWidth : 200;
      height = 60; 
    } else if (detailBlock){
		const flexContainer = canvas.parentElement; 
		width = flexContainer ? flexContainer.clientWidth : 500;
		height = 80;
	} else {
      width = projectTile ? projectTile.clientWidth - 30 : 350;
      height = 80;
    }

    canvas.width = width;
    canvas.height = height;

    const shapeOffset = 10;
    const leftMargin = 20 - shapeOffset;
    const rightMargin = 20 - shapeOffset;
    const usableWidth = width - leftMargin - rightMargin;

    const lineY = height / 2;

    const validatedY = lineY + (isLinearView ? 3 : 5);
    const actualY = lineY - (isLinearView ? 3 : 5);

    ctx.clearRect(0, 0, width, height);

    // Parse unformatted ISO dates. Formatted dates are only used for display.
    dateValues = dateValues || {};
    const validatedStart = parseDate(dateValues.validatedStartDate);
    const plannedStart = parseDate(dateValues.plannedStartDate);
    const realStart = parseDate(dateValues.realStartDate);
    const validatedEnd = parseDate(dateValues.validatedEndDate);
    const plannedEnd = parseDate(dateValues.plannedEndDate);
    const realEnd = parseDate(dateValues.realEndDate);
    const projectStart = realStart || plannedStart;
    const projectEnd = realEnd || plannedEnd;

    const parsedMilestones = milestones
      .map(m => {
        const validated = parseDate(m.validateddateiso);
        const planned = parseDate(m.plannedenddateiso);
        const real = parseDate(m.realenddateiso);
        
        return { 
          ...m, 
          validatedDateParsed: validated,
          plannedDateParsed: planned,
          realDateParsed: real
        };
      })
      .filter(m => m.validatedDateParsed || m.plannedDateParsed || m.realDateParsed);

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const allDates = [
      validatedStart,
      plannedStart,
      realStart,
      validatedEnd,
      plannedEnd,
      realEnd,
      today,
      ...parsedMilestones.map(m => m.validatedDateParsed).filter(Boolean),
      ...parsedMilestones.map(m => m.plannedDateParsed).filter(Boolean),
      ...parsedMilestones.map(m => m.realDateParsed).filter(Boolean)
    ].filter(Boolean);

    const minDate = new Date(Math.min(...allDates));
    const maxDate = new Date(Math.max(...allDates));
    const totalDuration = Math.max(maxDate - minDate, 1);

    function dateToX(date) {
      return leftMargin + ((date - minDate) / totalDuration) * usableWidth;
    }

    const todayX = dateToX(today);

    // Reset interactive elements
    interactiveElements = [];

    const startX = leftMargin - shapeOffset;
    const endX = width - rightMargin + shapeOffset;

    // Grey baseline outside the effective project period.
    ctx.beginPath();
    ctx.moveTo(startX, lineY);
    ctx.lineTo(endX, lineY);
    ctx.strokeStyle = "#999";
    ctx.lineWidth = 1;
    ctx.stroke();

    // Effective project period: real dates take precedence over planned dates.
    if (projectStart && projectEnd) {
      ctx.beginPath();
      ctx.moveTo(dateToX(projectStart), lineY);
      ctx.lineTo(dateToX(projectEnd), lineY);
      ctx.strokeStyle = "#44af69";
      ctx.lineWidth = 5;
      ctx.stroke();
    }

    // An early end is extended to the validated end with a thin green segment.
    if (projectEnd && validatedEnd && projectEnd < validatedEnd) {
      ctx.beginPath();
      ctx.moveTo(dateToX(projectEnd), lineY);
      ctx.lineTo(dateToX(validatedEnd), lineY);
      ctx.strokeStyle = "#44af69";
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // A late start is displayed as a thin red segment.
    if (validatedStart && projectStart && projectStart > validatedStart) {
      ctx.beginPath();
      ctx.moveTo(dateToX(validatedStart), lineY);
      ctx.lineTo(dateToX(projectStart), lineY);
      ctx.strokeStyle = "#f8333c";
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // A late end overlays the effective period with a thick red segment.
    if (validatedEnd && projectEnd && projectEnd > validatedEnd) {
      ctx.beginPath();
      ctx.moveTo(dateToX(validatedEnd), lineY);
      ctx.lineTo(dateToX(projectEnd), lineY);
      ctx.strokeStyle = "#f8333c";
      ctx.lineWidth = 5;
      ctx.stroke();
    }

    const todayLineHeight = isLinearView ? 14 : 14;
    ctx.beginPath();
    ctx.moveTo(todayX, validatedY - todayLineHeight);
    ctx.lineTo(todayX, actualY + todayLineHeight);
    ctx.strokeStyle = "orange";
    ctx.lineWidth = isLinearView ? 2 : 2;
    ctx.stroke();

//    if (!isLinearView) {
      const todayText = i18n('today');
      ctx.font = "9px Arial";
      ctx.textAlign = "center";
      const textWidth = ctx.measureText(todayText).width;
      const textX = Math.max(textWidth / 2 + 5, Math.min(todayX, width - textWidth / 2 - 5)); 

      ctx.fillStyle = "orange";
      ctx.fillText(todayText, textX, validatedY - 20);
//    }

    function drawMarker(ctx, x, y, direction, color, label, dateStr) {
      const lineLength = isLinearView ? 18 : 18;
      const radius = isLinearView ? 5 : 5;

      let circleY, lineStartY, lineEndY;

      if (direction === "up") {
        lineStartY = lineY;
        lineEndY = lineY - lineLength;
        circleY = lineEndY;
      } else {
        lineStartY = lineY;
        lineEndY = lineY + lineLength;
        circleY = lineEndY;
      }

      ctx.beginPath();
      ctx.moveTo(x, lineStartY);
      ctx.lineTo(x, lineEndY);
      ctx.strokeStyle = color;
      ctx.lineWidth = isLinearView ? 1.5 : 2;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(x, circleY, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();

      interactiveElements.push({
        x: x,
        y: circleY,
        radius: radius + 3, 
        label: label,
        date: dateStr,
        type:'marker',
      });
    }

    function drawTriangle(ctx, x, y, orientation, color, milestone) {
      const size = isLinearView ? 5 : 5;
      const offset = isLinearView ? 6 : 6;
      const isFilled = milestone.done == 1 || milestone.done == '1';

      ctx.beginPath();
      if (orientation === "up") {
        ctx.moveTo(x, lineY - offset - size);
        ctx.lineTo(x - size, lineY - offset + size);
        ctx.lineTo(x + size, lineY - offset + size);
      } else {
        ctx.moveTo(x, lineY + offset + size);
        ctx.lineTo(x - size, lineY + offset - size);
        ctx.lineTo(x + size, lineY + offset - size);
      }
      ctx.closePath();
      if (isFilled) {
        ctx.fillStyle = color;
        ctx.fill();
      } else {
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = isLinearView ? 1.5 : 2;
        ctx.stroke();
      }

      const centerY = orientation === "up" ? lineY - offset : lineY + offset;
      interactiveElements.push({
        x: x,
        y: centerY,
        radius: size + 3,
        label: milestone.name,
        date: milestone.dateOriginal, 
        id: milestone.id, 
        type: 'milestone',
        dateType: milestone.dateType,
        onClick: () => {}
      });
    }
    
    function getValidationColor(validated, planned) {
      if (!validated && planned) return '#44af69';
      if (validated && planned && planned > validated) return '#f8333c';
      return '#44af69';
    }
    
    const effectiveStartDate = realStart ? realStartDate : plannedStartDate;
    const effectiveEndDate = realEnd ? realEndDate : plannedEndDate;
    const startColor = getValidationColor(validatedStart, projectStart);
    const endColor = getValidationColor(validatedEnd, projectEnd);
    
    if (validatedStart)
      drawMarker(ctx, dateToX(validatedStart), validatedY, "down", startColor, i18n('colValidatedStart'), validatedStartDate);
    if (projectStart)
      drawMarker(ctx, dateToX(projectStart), actualY, "up", startColor, realStart ? i18n('colRealStart') : i18n('colPlannedStart'), effectiveStartDate);

    if (validatedEnd)
      drawMarker(ctx, dateToX(validatedEnd), validatedY, "down", endColor, i18n('colValidatedEnd'), validatedEndDate);
    if (projectEnd)
      drawMarker(ctx, dateToX(projectEnd), actualY, "up", endColor, realEnd ? i18n('colRealEnd') : i18n('colPlannedEnd'), effectiveEndDate);

    parsedMilestones.forEach(m => {
      let useCustomColor = false;
      let customColor = '#ffa64d';
      
      if (useColor && m.color) {
        useCustomColor = true;
        customColor = m.color;
      }
      
      let validationColor = '#44af69';
      let hasValidated = m.validatedDateParsed !== null && m.validatedDateParsed !== undefined;
      let hasPlanned = m.plannedDateParsed !== null && m.plannedDateParsed !== undefined;
      let hasReal = m.realDateParsed !== null && m.realDateParsed !== undefined;
      
      if (hasValidated && hasPlanned && m.plannedDateParsed > m.validatedDateParsed) {
        validationColor = '#f8333c';
      }
      
      const finalColor = useCustomColor ? customColor : validationColor;
      
      if (hasValidated) {
        const xValidated = dateToX(m.validatedDateParsed);
        drawTriangle(ctx, xValidated, lineY, "down", finalColor, { 
          ...m, 
          date: m.validatedDateParsed, 
          dateOriginal: m.validateddate,
          dateType: i18n('colValidated') 
        });
      }
      
      if (hasReal) {
        const xReal = dateToX(m.realDateParsed);
        drawTriangle(ctx, xReal, lineY, "up", finalColor, { 
          ...m, 
          date: m.realDateParsed, 
          dateOriginal: m.realenddate,
          dateType: i18n('colReal')
        });
      } else if (hasPlanned) {
        const xPlanned = dateToX(m.plannedDateParsed);
        drawTriangle(ctx, xPlanned, lineY, "up", finalColor, { 
          ...m, 
          date: m.plannedDateParsed, 
          dateOriginal: m.plannedenddate,
          dateType: i18n('colPlanned')
        });
      }
    });
  }
  
  // Setup tooltip 
  let tooltipDiv = document.getElementById(canvasId + '-tooltip');
  if (!tooltipDiv) {
    tooltipDiv = document.createElement('div');
    tooltipDiv.id = canvasId + '-tooltip';
    tooltipDiv.style.position = 'absolute';
    tooltipDiv.style.background = 'rgba(0, 0, 0, 0.8)';
    tooltipDiv.style.color = 'white';
    tooltipDiv.style.padding = '6px 10px';
    tooltipDiv.style.borderRadius = '4px';
    tooltipDiv.style.fontSize = '12px';
    tooltipDiv.style.pointerEvents = 'none';
    tooltipDiv.style.display = 'none';
    tooltipDiv.style.zIndex = '1000';
    tooltipDiv.style.whiteSpace = 'nowrap';
    document.body.appendChild(tooltipDiv);
  }

  // Event listeners
  canvas.addEventListener('mousemove', function(event) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    let found = false;

    for (let elem of interactiveElements) {
      const distance = Math.sqrt(Math.pow(mouseX - elem.x, 2) + Math.pow(mouseY - elem.y, 2));
      
      if (distance <= elem.radius) {
        let tooltipContent;
        if (elem.type == 'milestone' && elem.dateType) {
          tooltipContent = `<strong>${elem.label}</strong><br>${elem.dateType} : ${elem.date}`;
        } else {
          tooltipContent = `<strong>${elem.label}</strong><br>${elem.date}`;
        }

        tooltipDiv.innerHTML = tooltipContent;
        tooltipDiv.style.display = 'block';

        tooltipDiv.style.left = '-9999px';
        tooltipDiv.style.top = '-9999px';
        
        const tooltipRect = tooltipDiv.getBoundingClientRect();
        const tooltipWidth = tooltipRect.width;
        const tooltipHeight = tooltipRect.height;
        
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        let left = event.clientX + 10;
        let top = event.clientY - 30;
        if (left + tooltipWidth > viewportWidth) left = event.clientX - tooltipWidth - 10;
        if (left < 0) left = 10;
        if (top < 0) top = event.clientY + 20;
        if (top + tooltipHeight > viewportHeight) top = viewportHeight - tooltipHeight - 10;
        tooltipDiv.style.left = left + 'px';
        tooltipDiv.style.top = top + 'px';
        canvas.style.cursor = 'pointer';
        found = true;
        break;
      }
    }
    
    if (!found) {
      tooltipDiv.style.display = 'none';
      canvas.style.cursor = 'default';
    }
  });
  
  canvas.addEventListener('click', function(event) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    tooltipDiv.style.display = 'none';
    for (let elem of interactiveElements) {
      const distance = Math.sqrt(
        (mouseX - elem.x) * (mouseX - elem.x) +
        (mouseY - elem.y) * (mouseY - elem.y)
      );

      if (distance <= elem.radius) {
        if (elem.type=='milestone') directSelectProject('Milestone',elem.id,false,true);
        return; 
      }
    }
  });

  canvas.addEventListener('mouseleave', function() {
    tooltipDiv.style.display = 'none';
    canvas.style.cursor = 'default';
  });
  
  setTimeout(drawTimeline, 0);
  
  if (canvas.resizeObserver) {
    canvas.resizeObserver.disconnect();
  }
  
  const projectTile = canvas.closest('.project-tile');
  const projectRow = canvas.closest('.project-row');
  const observeElement = projectRow || projectTile;
  
  if (observeElement) {
    canvas.resizeObserver = new ResizeObserver(() => {
      drawTimeline();
    });
    canvas.resizeObserver.observe(observeElement);
  }
}

// Helper function to parse unformatted ISO dates (YYYY-MM-DD).
function parseDate(dateStr) {
  if (!dateStr || typeof dateStr !== 'string') return null;

  const parts = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|[ T])/);
  if (!parts) return null;

  const year = Number(parts[1]);
  const month = Number(parts[2]);
  const day = Number(parts[3]);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;

  date.setHours(0, 0, 0, 0);
  return date;
}

		

// ==================== PROGRESS CHART FUNCTIONs ====================
function progressChart(canvas, validated, real, left, planned, chartType, icon) {
  if (!canvas) return;
 
  const isLinearView = canvas.closest('.project-row') !== null;
  
  if (chartType == "technicalProgressCanvas") {
    var unitPorgress = planned;
    planned = validated;
  }
  
  const ctx = canvas.getContext('2d');
  const size = canvas.width;
  const centerX = size / 2;
  const centerY = isLinearView ? size * 0.4 : size / 2 ; 
  const outerRadius = size / 3;
  const innerRadius = size * 0.25;
  const strokeWidth = size / 15;

  const realColor = '#656565';
  const validatedColor = '#2b9eb3';
  const lightGrayColor = '#e8e8e8';

  if ((!validated || validated <= 0) && (!left || left <= 0) && (!real || real <= 0)) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.beginPath();
    ctx.arc(centerX, centerY, innerRadius, 0, 2 * Math.PI, false);
    ctx.lineWidth = strokeWidth;
    ctx.strokeStyle = lightGrayColor;
    ctx.stroke();

    if (icon) {
      let iconContainer = canvas.parentElement.querySelector('.chart-icon-container');
      if (!iconContainer) {
        iconContainer = document.createElement('div');
        iconContainer.className = 'chart-icon-container';
		const detailBlock = canvas.closest('.detail-milestone-block');
		if (detailBlock) {
		  iconContainer.style.cssText = 'position: absolute; top: ' + (isLinearView ? 35 : 45) + '%; left: calc(50% - 10px); transform: translate(-50%, -60%); pointer-events: none;';
		} else {
		  iconContainer.style.cssText = 'position: absolute; top: ' + (isLinearView ? 35 : 45) + '%; left: 50%; transform: translate(-50%, -60%); pointer-events: none;';
		}
        //iconContainer.style.cssText = 'position: absolute; top: ' + (isLinearView ? 35 : 45) +'%; left: 50%; transform: translate(-50%, -60%); pointer-events: none;';
        canvas.parentElement.style.position = 'relative';
        canvas.parentElement.appendChild(iconContainer);
      }
      iconContainer.innerHTML = icon;
      
      ctx.fillStyle = '#cccccc';
      ctx.font = isLinearView ? 'bold 16px Arial' : 'bold 24px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('—', centerX, centerY + (isLinearView ? 8 : 13));
    } else {
      ctx.fillStyle = '#cccccc';
      ctx.font = isLinearView ? 'bold 16px Arial' : 'bold 24px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('—', centerX, centerY);
    }

    if (planned !== undefined && planned !== null) {
      ctx.fillStyle = '#666666';
      ctx.font = isLinearView ? '9px Arial' : '12px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      var plannedFormated = planned;
      if (chartType=='workProgressCanvas'){
        var paramUnit=window.top.paramWorkUnit;
        if (paramUnit == 'hours') unit =`${i18n('shortHour')}`;
        else unit =`${i18n('shortDay')}`;
        plannedFormated = workFormatter(planned,null,false,true);
      } else if (chartType=='budgetProgressCanvas') {
        unit = window.top.paramCurrency;
        plannedFormated = costFormatter(planned,null,false,true);
      } else if (chartType=='technicalProgressCanvas') {
        if (planned == 1) plannedFormated = planned + ' ' +i18n('colUnit');
        else plannedFormated = planned + ' ' +i18n('units');
      } else if (chartType=='financialProgressCanvas') {
        plannedFormated = costFormatter(real,null,false,true);
      }
      if (typeof plannedFormated === 'string' && plannedFormated.includes('<')) {
        var tempDiv = document.createElement('div');
        tempDiv.innerHTML = plannedFormated;
        plannedFormated = tempDiv.textContent || tempDiv.innerText || plannedFormated;
      }
      
      var fullText = '';
      if (chartType=='budgetProgressCanvas' || chartType=='workProgressCanvas') {
        fullText = i18n('colReassessed').charAt(0).toUpperCase() + i18n('colReassessed').slice(1)+' : ' + plannedFormated;
      } else if (chartType=='technicalProgressCanvas' || chartType=='financialProgressCanvas') {
        fullText = i18n('colToRealise').charAt(0).toUpperCase() + i18n('colToRealise').slice(1)+' : ' + plannedFormated;
      }
      
      const maxWidth = size - 6; 
      const textWidth = ctx.measureText(fullText).width;
      
      if (textWidth > maxWidth) {
        const parts = fullText.split(' : ');
        if (parts.length === 2) {
          const lineHeight = isLinearView ? 10 : 12;
          ctx.fillText(parts[0] + ' :', centerX, size - (isLinearView ? 22 : 21));
          ctx.fillText(parts[1], centerX, size - (isLinearView ? 22 : 21) + lineHeight);
        } else {
          ctx.fillText(fullText, centerX, size - (isLinearView ? 12 : 11));
        }
      } else {
        ctx.fillText(fullText, centerX, size - (isLinearView ? 12 : 11));
      }
    }

    canvas.chartData = {
      noData: true,
      chartType: chartType
    };
    setupTooltipNoData(canvas, chartType);
    return;
  }

  const baseValue = (validated && validated > 0) ? validated : (real + left);
  const remainingColor = (!validated || validated <= 0) ? '#44af69' : ((real + left > validated) ? '#f8333c' : '#44af69');
  
  const realAngle = (real / baseValue) * Math.PI;
  const leftAngle = (left === 0 || !left) ? Math.PI : (left / baseValue) * Math.PI;
  const progress = (chartType=='technicalProgressCanvas') ? unitPorgress : Math.round((real / baseValue) * 100);

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.beginPath();
  ctx.arc(centerX, centerY, outerRadius, 0, Math.PI, false);
  ctx.lineWidth = strokeWidth;
  ctx.strokeStyle = lightGrayColor;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(centerX, centerY, outerRadius, Math.PI, 2 * Math.PI, false);
  ctx.lineWidth = strokeWidth;
  ctx.strokeStyle = (validated && validated > 0) ? validatedColor : '#e8e8e8' ;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(centerX, centerY, innerRadius, 0, 2 * Math.PI, false);
  ctx.lineWidth = strokeWidth;
  ctx.strokeStyle = lightGrayColor;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(centerX, centerY, innerRadius, Math.PI, Math.PI + realAngle, false);
  ctx.lineWidth = strokeWidth;
  ctx.strokeStyle = realColor;
  ctx.stroke();

  const leftColor = (left === 0 || !left || !validated || validated <= 0) ? '#44af69' : remainingColor;
  if (left){
    ctx.beginPath();
    ctx.arc(centerX, centerY, innerRadius, Math.PI + realAngle, Math.PI + realAngle + leftAngle, false);
    ctx.lineWidth = strokeWidth;
    ctx.strokeStyle = leftColor;
    ctx.stroke();
  }

  // Percentage text in the centre
  if (icon) {
    ctx.fillStyle = '#2c3e50';
    ctx.font = isLinearView ? 'bold 12px Arial' : 'bold 16px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(progress + '%', centerX, centerY + (isLinearView ? 10 : 13));
    let iconContainer = canvas.parentElement.querySelector('.chart-icon-container');
    if (!iconContainer) {
      iconContainer = document.createElement('div');
      iconContainer.className = 'chart-icon-container';
	  const detailBlock = canvas.closest('.detail-milestone-block');
	  if (detailBlock) {
	    iconContainer.style.cssText = 'position: absolute; top:  45%; left: calc(50% - 10px); transform: translate(-50%, -60%); pointer-events: none;';
	  } else {
	    iconContainer.style.cssText = 'position: absolute; top: ' + (isLinearView ? 35 : 45) + '%; left: 50%; transform: translate(-50%, -60%); pointer-events: none;';
	  }
	  //iconContainer.style.cssText = 'position: absolute; top:' + (isLinearView ? 35 : 45) +'%; left: 50%; transform: translate(-50%, -60%); pointer-events: none;';
      canvas.parentElement.style.position = 'relative';
      canvas.parentElement.appendChild(iconContainer);
    }
    iconContainer.innerHTML = icon;
  } else {
    ctx.fillStyle = '#2c3e50';
    ctx.font = isLinearView ? 'bold 14px Arial' : 'bold 20px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(progress + '%', centerX, centerY + 3);
  }

  // Planned
  if (planned !== undefined && planned !== null) {
    ctx.fillStyle = '#666666';
    ctx.font = isLinearView ? '10px Arial' : '12px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    var plannedFormated = planned;
    if (chartType=='workProgressCanvas'){
      var paramUnit=window.top.paramWorkUnit;
      if (paramUnit == 'hours') unit =`${i18n('shortHour')}`;
      else unit =`${i18n('shortDay')}`;
      plannedFormated = workFormatter(planned,null,false,true);
    } else if (chartType=='budgetProgressCanvas') {
      unit = window.top.paramCurrency;
      plannedFormated = costFormatter(planned,null,false,true);
    } else if (chartType=='technicalProgressCanvas') {
      if (planned == 1) plannedFormated = planned + ' ' +i18n('colUnit');
      else plannedFormated = planned + ' ' +i18n('units');
    } else if (chartType=='financialProgressCanvas') {
      plannedFormated = costFormatter(real,null,false,true);
    }
    if (typeof plannedFormated === 'string' && plannedFormated.includes('<')) {
      var tempDiv = document.createElement('div');
      tempDiv.innerHTML = plannedFormated;
      plannedFormated = tempDiv.textContent || tempDiv.innerText || plannedFormated;
    }
    
    var fullText = '';
    if (chartType=='budgetProgressCanvas' || chartType=='workProgressCanvas') {
      fullText = i18n('colReassessed').charAt(0).toUpperCase() + i18n('colReassessed').slice(1)+' : ' + plannedFormated;
    } else if (chartType=='technicalProgressCanvas' || chartType=='financialProgressCanvas') {
      fullText = i18n('colToRealise').charAt(0).toUpperCase() + i18n('colToRealise').slice(1)+' : ' + plannedFormated;
    }
    
    const maxWidth = size - 6;
    const textWidth = ctx.measureText(fullText).width;
    
    if (textWidth > maxWidth) {
      const parts = fullText.split(' : ');
      if (parts.length === 2) {
        const lineHeight = isLinearView ? 10 : 12;
        ctx.fillText(parts[0] + ' :', centerX, size - (isLinearView ? 22 : 21));
        ctx.fillText(parts[1], centerX, size - (isLinearView ? 22 : 21) + lineHeight);
      } else {
        ctx.fillText(fullText, centerX, size - (isLinearView ? 12 : 11));
      }
    } else {
      ctx.fillText(fullText, centerX, size - (isLinearView ? 12 : 11));
    }
  }

  canvas.chartData = {
    centerX, centerY, outerRadius, innerRadius, strokeWidth,
    realAngle, leftAngle, validated, real, left, textRadius: 25, progress,
    noData: false
  };
  setupTooltip(canvas, chartType);
}

function setupTooltip(canvas,chartType) {
  var paramUnit=window.top.paramWorkUnit;
  // Check if tooltip already exists
  if (canvas.tooltipSetup) return;
  
  // Create tooltip element if it doesn't exist
  let tooltip = document.getElementById('tooltip_projectDash');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'tooltip_projectDash';
    tooltip.style.cssText = `
      position: fixed;
      background-color: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 14px;
      pointer-events: none;
      z-index: 10000;
      opacity: 0;
      transition: opacity 0.2s;
	  white-space: nowrap;
    `;
    document.body.appendChild(tooltip);
  }
  
  function positionTooltip(e, tooltipText) {
    if (!tooltipText) {
      tooltip.style.opacity = '0';
      return;
    }
    tooltip.innerHTML  = tooltipText;
    tooltip.style.opacity = '1';
    // Get tooltip dimensions (need to make it visible first to measure)
    tooltip.style.left = '-9999px';
    tooltip.style.top = '-9999px';
    tooltip.style.opacity = '1';
    const tooltipRect = tooltip.getBoundingClientRect();
    const tooltipWidth = tooltipRect.width;
    const tooltipHeight = tooltipRect.height; 
    // Get viewport dimensions
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    // Default position (right and above cursor)
    let left = e.clientX + 10;
    let top = e.clientY - 30;
    // Check if tooltip goes beyond right / left / top /bottom edge
    if (left + tooltipWidth > viewportWidth) left = e.clientX - tooltipWidth - 10; 
    if (left < 0)  left = 10;
    if (top < 0) top = e.clientY + 20; 
    if (top + tooltipHeight > viewportHeight) top = viewportHeight - tooltipHeight - 10; 
       
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }
  
  // Mouse move handler
  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;  
    if (!canvas.chartData) return;
    const { centerX, centerY, outerRadius, innerRadius, strokeWidth, realAngle, leftAngle, validated, real, left, textRadius, progress} = canvas.chartData;
    let tooltipText = '';
	var unit ='';
	var textProgress = `${i18n('progress')}`;
    if (chartType=='workProgressCanvas'){
      if (paramUnit == 'hours') unit =`${i18n('shortHour')}`;
	  else unit =`${i18n('shortDay')}`;
	  textProgress = `${i18n('sectionWork')}`;
	} else if (chartType=='budgetProgressCanvas') {
	  unit = window.top.paramCurrency;
	  textProgress = `${i18n('Budget')}`;
	} else if (chartType=='technicalProgressCanvas') {
      textProgress = `${i18n('menuTechnicalProgress')}`;
  	} else if (chartType=='financialProgressCanvas') {
	  textProgress = `${i18n('menuInvoice')}`;
	}
	// Check if the mouse is near the center text
	const distanceToCenter = Math.sqrt(Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2));
	if (distanceToCenter < textRadius)  tooltipText = textProgress + ` : ${progress}%`;
	
	const formatValueWithUnit = (value) => {
	  var formattedValue;
	  if (chartType === 'budgetProgressCanvas') {
	    formattedValue = costFormatter(value);
	  } else if (chartType == 'workProgressCanvas') {
	    formattedValue = workFormatter(value);
	  } else if (chartType == 'technicalProgressCanvas') {
	    if (value == 1) return `${(value)}` + ' ' + `${i18n('unit')}`;
	    else return `${(value)}` + ' ' + `${i18n('units')}`;
	  } else if (chartType == 'financialProgressCanvas') {
		formattedValue = costFormatter(value);
	  }
	  if (typeof formattedValue === 'string' && formattedValue.includes('<')) {
	    var tempDiv = document.createElement('div');
	    tempDiv.innerHTML = formattedValue;
	    formattedValue = tempDiv.textContent || tempDiv.innerText || formattedValue;
	  }  
	  return formattedValue;
	};
	
	// Check validated arc
	if (isPointOnArc(x, y, centerX, centerY, outerRadius, Math.PI, 2 * Math.PI, strokeWidth)) {
	  if (chartType == 'financialProgressCanvas') tooltipText = `${i18n('colCA').charAt(0).toUpperCase() + i18n('colCA').slice(1)} : ${formatValueWithUnit(validated)}`;
	  else tooltipText = `${i18n('colValidated').charAt(0).toUpperCase() + i18n('colValidated').slice(1)} : ${formatValueWithUnit(validated)}`;
	}
	// Check real arc
	else if (isPointOnArc(x, y, centerX, centerY, innerRadius, Math.PI, Math.PI + realAngle, strokeWidth)) {
	  if (chartType == 'financialProgressCanvas') tooltipText = `${i18n('colBilled').charAt(0).toUpperCase() + i18n('colBilled').slice(1)} : ${formatValueWithUnit(real)}`;
	  else tooltipText = `${i18n('colReal').charAt(0).toUpperCase() + i18n('colReal').slice(1)} : ${formatValueWithUnit(real)}`;
	}
	// Check left arc
	else if (isPointOnArc(x, y, centerX, centerY, innerRadius, Math.PI + realAngle, Math.PI + realAngle + leftAngle, strokeWidth)) {
	  if (chartType == 'financialProgressCanvas') tooltipText = `${i18n('billingTypeN').charAt(0).toUpperCase() + i18n('billingTypeN').slice(1)} : ${formatValueWithUnit(left)}`;
	  else tooltipText = `${i18n('colLeft').charAt(0).toUpperCase() + i18n('colLeft').slice(1)} : ${formatValueWithUnit(left)}`;
	}
    
    positionTooltip(e, tooltipText);
  });
  
  // Mouse leave handler
  canvas.addEventListener('mouseleave', () => {
    tooltip.style.opacity = '0';
  });
  
  canvas.tooltipSetup = true;
}
      
// Function to check whether a point lies on an arc
function isPointOnArc(x, y, centerX, centerY, radius, startAngle, endAngle, strokeWidth) {
  const dx = x - centerX;
  const dy = y - centerY;
  const distance = Math.sqrt(dx * dx + dy * dy);
  const angle = Math.atan2(dy, dx);
            
  // Normalise the angle between -PI and PI
  let normalizedAngle = angle;
  if (normalizedAngle < startAngle - Math.PI) normalizedAngle += 2 * Math.PI;
  if (normalizedAngle > endAngle + Math.PI) normalizedAngle -= 2 * Math.PI;        
  const isInRadius = distance >= radius - strokeWidth / 2 && distance <= radius + strokeWidth / 2;
  const isInAngle = normalizedAngle >= startAngle && normalizedAngle <= endAngle;
            
  return isInRadius && isInAngle;
}

function progressChartStatus(canvas, closed, done, todo, total, chartType, icon) {
  if (!canvas) return;
 
  const isLinearView = canvas.closest('.project-row') !== null;
  
  const ctx = canvas.getContext('2d');
  const size = canvas.width;
  const centerX = size / 2;
  const centerY = isLinearView ? size * 0.4 : size / 2; 
  const outerRadius = size / 3;
  const innerRadius = size * 0.25;
  const strokeWidth = size / 15;
            
  const closedColor = '#2c3e50';
  const doneColor = '#44af69';
  const todoColor = '#f8333c';
  const totalColor = '#2b9eb3';
  const lightGrayColor = '#e8e8e8';
  
  if (!total || total <= 0) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.beginPath();
    ctx.arc(centerX, centerY, innerRadius, 0, 2 * Math.PI, false);
    ctx.lineWidth = strokeWidth;
    ctx.strokeStyle = lightGrayColor;
    ctx.stroke();
    
    if (icon) {
      let iconContainer = canvas.parentElement.querySelector('.chart-icon-container');
      if (!iconContainer) {
        iconContainer = document.createElement('div');
        iconContainer.className = 'chart-icon-container';
        iconContainer.style.cssText = 'position: absolute; top: ' + (isLinearView ? 35 : 45) +'%; left: 50%; transform: translate(-50%, -60%); pointer-events: none;';
        canvas.parentElement.style.position = 'relative';
        canvas.parentElement.appendChild(iconContainer);
      }
      iconContainer.innerHTML = icon;
      
      ctx.fillStyle = '#cccccc';
      ctx.font = isLinearView ? 'bold 16px Arial' : 'bold 24px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('—', centerX, centerY + (isLinearView ? 8 : 13));
    } else {
      ctx.fillStyle = '#cccccc';
      ctx.font = isLinearView ? 'bold 16px Arial' : 'bold 24px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('—', centerX, centerY);
    }
    
    ctx.fillStyle = '#666666';
    ctx.font = isLinearView ? '9px Arial' : '12px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    
    var fullText = '';
    if (chartType=='riskProgressCanvas') {
      fullText = i18n('colCountTotal').charAt(0).toUpperCase() + i18n('colCountTotal').slice(1)+' : ' + total + ' '+ i18n('Risk').charAt(0).toLowerCase() + i18n('Risk').slice(1);
    } else if (chartType=='ticketProgressCanvas') {
      fullText = i18n('colCountTotal').charAt(0).toUpperCase() + i18n('colCountTotal').slice(1)+' : ' + total + ' '+ i18n('Ticket').charAt(0).toLowerCase() + i18n('Ticket').slice(1);
    } else if (chartType=='requirementProgressCanvas') {
      fullText = i18n('colCountTotal').charAt(0).toUpperCase() + i18n('colCountTotal').slice(1)+' : ' + total + ' '+ i18n('Requirement').charAt(0).toLowerCase() + i18n('Requirement').slice(1);
    } else if (chartType=='userStoryProgressCanvas') {
      fullText = i18n('colCountTotal').charAt(0).toUpperCase() + i18n('colCountTotal').slice(1)+' : ' + total + ' '+ i18n('UserStory').charAt(0).toLowerCase() + i18n('UserStory').slice(1);
    }
    
    const maxWidth = size - 6;
    const textWidth = ctx.measureText(fullText).width;
    
    if (textWidth > maxWidth) {
      const parts = fullText.split(' : ');
      if (parts.length === 2) {
        const lineHeight = isLinearView ? 10 : 12;
        ctx.fillText(parts[0] + ' :', centerX, size - (isLinearView ? 22 : 21));
        ctx.fillText(parts[1], centerX, size - (isLinearView ? 22 : 21) + lineHeight);
      } else {
        ctx.fillText(fullText, centerX, size - (isLinearView ? 12 : 11));
      }
    } else {
      ctx.fillText(fullText, centerX, size - (isLinearView ? 12 : 11));
    }
    
    canvas.chartData = {
      noData: true,
      chartType: chartType
    };
    setupTooltipNoData(canvas,chartType);

    return;
  }  
  const closedAngle = (closed / total) * 2 * Math.PI;
  const doneAngle = (done / total) * 2 * Math.PI;
  const todoAngle = (todo / total) * 2 * Math.PI;
  const progress = Math.round(((done + closed) / total) * 100);        
  
  ctx.clearRect(0, 0, canvas.width, canvas.height);       
  
  ctx.beginPath();
  ctx.arc(centerX, centerY, outerRadius, 0, 2 * Math.PI, false);
  ctx.lineWidth = strokeWidth;
  ctx.strokeStyle = totalColor;
  ctx.stroke();          
  
  ctx.beginPath();
  ctx.arc(centerX, centerY, innerRadius, 0, closedAngle, false);
  ctx.lineWidth = strokeWidth;
  ctx.strokeStyle = closedColor;
  ctx.stroke();        
  
  ctx.beginPath();
  ctx.arc(centerX, centerY, innerRadius, closedAngle, closedAngle + doneAngle, false);
  ctx.lineWidth = strokeWidth;
  ctx.strokeStyle = doneColor;
  ctx.stroke();          
  
  ctx.beginPath();
  ctx.arc(centerX, centerY, innerRadius, closedAngle + doneAngle, closedAngle + doneAngle + todoAngle, false);
  ctx.lineWidth = strokeWidth;
  ctx.strokeStyle = todoColor;
  ctx.stroke();           
  
  if (icon) {
    ctx.fillStyle = '#2c3e50';
    ctx.font = isLinearView ? 'bold 12px Arial' : 'bold 16px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(progress + '%', centerX, centerY + (isLinearView ? 10 : 13));
    let iconContainer = canvas.parentElement.querySelector('.chart-icon-container');
    if (!iconContainer) {
      iconContainer = document.createElement('div');
      iconContainer.className = 'chart-icon-container';
      iconContainer.style.cssText = 'position: absolute; top: ' + (isLinearView ? 35 : 45) +'%; left: 50%; transform: translate(-50%, -60%); pointer-events: none;';
      canvas.parentElement.style.position = 'relative';
      canvas.parentElement.appendChild(iconContainer);
    }
    iconContainer.innerHTML = icon;
  } else {
    ctx.fillStyle = '#2c3e50';
    ctx.font = isLinearView ? 'bold 14px Arial' : 'bold 20px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(progress + '%', centerX, centerY + 3);
  }   
  
  if (total) {
    ctx.fillStyle = '#666666';
    ctx.font = isLinearView ? '10px Arial' : '12px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    
    var text = "";
    if (chartType=='riskProgressCanvas') text = total>1 ?i18n('menuRisk').charAt(0).toLowerCase() + i18n('menuRisk').slice(1) : i18n('Risk').charAt(0).toLowerCase() + i18n('Risk').slice(1);
    else if (chartType=='ticketProgressCanvas') text = total>1 ?i18n('menuTicket').charAt(0).toLowerCase() + i18n('menuTicket').slice(1) : i18n('Ticket').charAt(0).toLowerCase() + i18n('Ticket').slice(1);
    else if (chartType=='requirementProgressCanvas') text = total>1 ?i18n('menuRequirement').charAt(0).toLowerCase() + i18n('menuRequirement').slice(1) : i18n('Requirement').charAt(0).toLowerCase() + i18n('Requirement').slice(1);
    else if (chartType=='userStoryProgressCanvas') text = total>1 ?i18n('menuUserStory').charAt(0).toLowerCase() + i18n('menuUserStory').slice(1) : i18n('UserStory').charAt(0).toLowerCase() + i18n('UserStory').slice(1);
    
    var fullText = i18n('colCountTotal').charAt(0).toUpperCase() + i18n('colCountTotal').slice(1)+' : ' + total + ' '+ text;
    
    const maxWidth = size - 10;
    const textWidth = ctx.measureText(fullText).width;
    
    if (textWidth > maxWidth) {
      const parts = fullText.split(' : ');
      if (parts.length === 2) {
        const lineHeight = isLinearView ? 10 : 12;
        ctx.fillText(parts[0] + ' :', centerX, size - (isLinearView ? 22 : 21));
        ctx.fillText(parts[1], centerX, size - (isLinearView ? 22 : 21) + lineHeight);
      } else {
        ctx.fillText(fullText, centerX, size - (isLinearView ? 12 : 11));
      }
    } else {
      ctx.fillText(fullText, centerX, size - (isLinearView ? 12 : 11));
    }
  }
      
  canvas.chartData = {
    centerX, centerY, outerRadius, innerRadius, strokeWidth,
    closedAngle, doneAngle, todoAngle, total, closed, done, todo, textRadius: 25, progress
  };
  setupTooltipStatus(canvas,chartType);
}

function setupTooltipStatus(canvas,chartType) {
  // Check if tooltip already exists
  if (canvas.tooltipSetup) return;
  // Create tooltip element if it doesn't exist
  let tooltip = document.getElementById('tooltip_projectDash');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'tooltip_projectDash';
    tooltip.style.cssText = `
      position: fixed;
      background-color: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 14px;
      pointer-events: none;
      z-index: 10000;
      opacity: 0;
      transition: opacity 0.2s;
      white-space: nowrap;
    `;
    document.body.appendChild(tooltip);
  }
  
  function positionTooltip(e, tooltipText) {
    if (!tooltipText) {
      tooltip.style.opacity = '0';
      return;
    }
    tooltip.textContent = tooltipText;
    tooltip.style.opacity = '1';
    tooltip.style.left = '-9999px';
    tooltip.style.top = '-9999px';
    tooltip.style.opacity = '1';
    const tooltipRect = tooltip.getBoundingClientRect();
    const tooltipWidth = tooltipRect.width;
    const tooltipHeight = tooltipRect.height; 
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    let left = e.clientX + 10;
    let top = e.clientY - 30;
    if (left + tooltipWidth > viewportWidth) left = e.clientX - tooltipWidth - 10; 
    if (left < 0) left = 10;
    if (top < 0) top = e.clientY + 20; 
    if (top + tooltipHeight > viewportHeight) top = viewportHeight - tooltipHeight - 10; 
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }
  
  // Mouse move handler
  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;  
    if (!canvas.chartData) return;
    const { centerX, centerY, outerRadius, innerRadius, strokeWidth, closedAngle, doneAngle, todoAngle, total, closed, done, todo, textRadius, progress} = canvas.chartData;
    let tooltipText = '';
    // Check if the mouse is near the center text
    const distanceToCenter = Math.sqrt(Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2));
    if (distanceToCenter < textRadius) {
      if (chartType == 'riskProgressCanvas') tooltipText = `${i18n('menuRiskManagement').charAt(0).toUpperCase() + i18n('menuRiskManagement').slice(1)} : ${progress}%`;
	  else if (chartType == 'ticketProgressCanvas') tooltipText = `${i18n('sectionTicket').charAt(0).toUpperCase() + i18n('sectionTicket').slice(1)} : ${progress}%`;
	  else if (chartType == 'requirementProgressCanvas') tooltipText = `${i18n('menuRequirementsManagement').charAt(0).toUpperCase() + i18n('menuRequirementsManagement').slice(1)} : ${progress}%`;
	  else if (chartType == 'userStoryProgressCanvas') tooltipText = `${i18n('sectionUserStory').charAt(0).toUpperCase() + i18n('sectionUserStory').slice(1)} : ${progress}%`;
    }
    // Check total arc (outer)
    else if (isPointOnArcRisk(x, y, centerX, centerY, outerRadius, 0, 2 * Math.PI, strokeWidth)) {
      tooltipText = `${i18n('colCountTotal').charAt(0).toUpperCase() + i18n('colCountTotal').slice(1)} : ${total}`;
    }
    // Check closed arc
    else if (isPointOnArcRisk(x, y, centerX, centerY, innerRadius, 0, closedAngle, strokeWidth)) {
      tooltipText = `${i18n('idle').charAt(0).toUpperCase() + i18n('idle').slice(1)} : ${closed}`;
    }
    // Check done arc
    else if (isPointOnArcRisk(x, y, centerX, centerY, innerRadius, closedAngle, closedAngle + doneAngle, strokeWidth)) {
      tooltipText = `${i18n('colDone').charAt(0).toUpperCase() + i18n('colDone').slice(1)} : ${done}`;
    }
    // Check todo arc
    else if (isPointOnArcRisk(x, y, centerX, centerY, innerRadius, closedAngle + doneAngle, closedAngle + doneAngle + todoAngle, strokeWidth)) {
      tooltipText = `${i18n('titleNbTodo').charAt(0).toUpperCase() + i18n('titleNbTodo').slice(1)} : ${todo}`;
    }
    positionTooltip(e, tooltipText);
  });
  
  // Mouse leave handler
  canvas.addEventListener('mouseleave', () => {
    tooltip.style.opacity = '0';
  });
  canvas.tooltipSetup = true;
}
        
// Function to check whether a point lies on an arc for risks (full circle)
function isPointOnArcRisk(x, y, centerX, centerY, radius, startAngle, endAngle, strokeWidth) {
  const dx = x - centerX;
  const dy = y - centerY;
  const distance = Math.sqrt(dx * dx + dy * dy);
  const angle = Math.atan2(dy, dx);        
  let normalizedAngle = angle;
  if (normalizedAngle < 0) normalizedAngle += 2 * Math.PI;         
  const isInRadius = distance >= radius - strokeWidth / 2 && distance <= radius + strokeWidth / 2;
  const isInAngle = normalizedAngle >= startAngle && normalizedAngle <= endAngle;   
  return isInRadius && isInAngle;
}
        
function adjustChartSizes(tileElement) {
  const container = tileElement.querySelector('.tile-progress-charts');
  if (!container) return;
  
  const allChartDivs = container.querySelectorAll('.tile-work-progress, .tile-budget-progress, .tile-risks-progress, .tile-technical-progress, .tile-financial-progress,.tile-tickets-progress, .tile-requirements-progress, .tile-userstories-progress');
  let visibleCount = 0;
  allChartDivs.forEach(function(div) {
    var style = window.getComputedStyle(div);
    if (style.display !== 'none') {
      visibleCount++;
    }
  });
  container.classList.remove('charts-count-1', 'charts-count-2', 'charts-count-3');
  container.classList.add('charts-count-' + visibleCount);

  const tileWidth = tileElement.clientWidth;
  const gap = 5;

  let size;
  if (visibleCount === 0) {
    return;
  } else if (visibleCount === 1) {
    size = Math.min(150, tileWidth * 0.5);
  } else if (visibleCount === 2) {
    size = Math.min(150, (tileWidth - gap) / 2);
  } else {
    size = Math.min(150, (tileWidth - gap) / 3);
  }
  
  size = Math.max(100, size);
  
  const canvases = container.querySelectorAll('canvas'); 
  canvases.forEach(function(canvas) {
    if (canvas.parentElement.style.display !== 'none') {
      canvas.width = size;
      canvas.height = size;
    }
  });
}

function redrawChartsForTile(tileElement) {
  var projectId = tileElement.getAttribute('data-project-id');
  if (!projectId) return;
  var project = null;
  var projectList = dbd.getProjectList();
  for (var i = 0; i < projectList.length; i++) {
    if (projectList[i].getId() == projectId) {
      project = projectList[i];
      break;
    }
  }
  if (!project) return;
  
  var isLinearView = getDashboardParameter('linearViewDashboard');
  
  var workProgressId = "workProgress-" + project.getId();
  var workProgressCanvas = document.getElementById(workProgressId);
  if (workProgressCanvas) {
  	progressChart(workProgressCanvas, project.getWorkValidated(), project.getWorkReal(), project.getWorkLeft(), project.getWorkPlanned(), 'workProgressCanvas', '<div class="iconImputation16 imageColorNewGui iconImputation iconSize16"></div>');
  }
  	    
  var budgetProgressId = "budgetProgress-" + project.getId();
  var budgetProgressCanvas = document.getElementById(budgetProgressId);
  if (budgetProgressCanvas) {
  	progressChart(budgetProgressCanvas, project.getTotalValidatedCost(), project.getTotalRealCost(), project.getTotalLeftCost(), project.getTotalPlannedCost(), 'budgetProgressCanvas', '<div class="iconExpenses16 imageColorNewGui iconExpenses iconSize16"></div>');
  }
  	    
  var risksProgressId = "risksProgress-" + project.getId();
  var risksProgressCanvas = document.getElementById(risksProgressId);
  if (risksProgressCanvas) {
  	progressChartStatus(risksProgressCanvas, project.getClosedRisk(), project.getDoneRisk(), project.getTodoRisk(), project.getTotalRisk(), 'riskProgressCanvas', '<div class="iconCriticality16 imageColorNewGui iconCriticality iconSize16"></div>');
  }

  var technicalProgressId = "technicalProgress-" + project.getId();
  var technicalProgressCanvas = document.getElementById(technicalProgressId);
  if (technicalProgressCanvas) {
  	progressChart(technicalProgressCanvas, project.getUnitToRealise(), project.getUnitRealised(), project.getUnitLeft(), project.getUnitProgress(), 'technicalProgressCanvas', '<div class="iconProgress16 imageColorNewGui iconProgress iconSize16"></div>');
  }
  
  var financialProgressId = "financialProgress-" + project.getId();
  var financialProgressCanvas = document.getElementById(financialProgressId);
  if (financialProgressCanvas) {
    progressChart(financialProgressCanvas, project.getRevenue(), project.getInvoiced(), project.getToBeBilled(), project.getPlannedFinancial(), 'financialProgressCanvas', '<div class="iconBill16 imageColorNewGui iconBill iconSize16"></div>');
  }
  		
  var ticketsProgressId = "ticketsProgress-" + project.getId();
  var ticketsProgressCanvas = document.getElementById(ticketsProgressId);
  if (ticketsProgressCanvas) {
  	progressChartStatus(ticketsProgressCanvas, project.getClosedTicket(), project.getDoneTicket(), project.getTodoTicket(), project.getTotalTicket(), 'ticketProgressCanvas', '<div class="iconTicket16 imageColorNewGui iconTicket iconSize16"></div>');
  }
  		
  var requirementsProgressId = "requirementsProgress-" + project.getId();
  var requirementsProgressCanvas = document.getElementById(requirementsProgressId);
  if (requirementsProgressCanvas) {
  	progressChartStatus(requirementsProgressCanvas, project.getClosedRequirement(), project.getDoneRequirement(), project.getTodoRequirement(), project.getTotalRequirement(), 'requirementProgressCanvas', '<div class="iconRequirement16 imageColorNewGui iconRequirement iconSize16"></div>');
  }
  		
  var userStoriesProgressId = "userStoriesProgress-" + project.getId();
  var userStoriesProgressCanvas = document.getElementById(userStoriesProgressId);
  if (userStoriesProgressCanvas) {
  	 progressChartStatus(userStoriesProgressCanvas, project.getClosedUserStory(), project.getDoneUserStory(), project.getTodoUserStory(), project.getTotalUserStory(), 'userStoryProgressCanvas', '<div class="iconUserStory16 imageColorNewGui iconUserStory iconSize16"></div>');
  }
  
  var timelineId = "timeline-" + project.getId();
  var timelineCanvas = document.getElementById(timelineId);
  if (timelineCanvas && isLinearView) {
    let elementProject = document.getElementById(isLinearView ? "projectRow_" + project.getId() : "project_" + project.getId());
    if (elementProject) {
      let valueProject = elementProject.getAttribute("data-typeMilestone");
      var filteredMilestones = filterMilestonesByType(project.getMilestones(), valueProject);
      var useColorMilestone = getDashboardParameter('colorMilestone');     
      createTimeline(timelineId, project.getValidatedStartDate(), project.getPlannedStartDate(), project.getRealStartDate(), project.getValidatedEndDate(), project.getPlannedEndDate(), project.getRealEndDate(), filteredMilestones, useColorMilestone, project.getTimelineDateValues());
    }
  }
  
}

function setupTooltipDashboard(element, getContentCallback) {
  if (element.tooltipSetup) return;
  let tooltip = document.getElementById('tooltip_projectDash');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'tooltip_projectDash';
    tooltip.style.cssText = `
      position: fixed;
      background-color: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 14px;
      pointer-events: none;
      z-index: 10000;
      opacity: 0;
      transition: opacity 0.2s;
      white-space: normal;
      max-width: 300px;
    `;
    document.body.appendChild(tooltip);
  }

  // Function to position tooltip
  function positionTooltip(e, content) {
    if (typeof content === 'string') {
      tooltip.textContent = content;
    } else {
      tooltip.innerHTML = content;
    }
    // Get tooltip dimensions
    const tooltipRect = tooltip.getBoundingClientRect();
    const tooltipWidth = tooltipRect.width;
    const tooltipHeight = tooltipRect.height;
    // Get viewport dimensions
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    // Default position (right and above cursor)
    let left = e.clientX + 10;
    let top = e.clientY - 30;
    // Check if tooltip goes beyond right edge
    if (left + tooltipWidth > viewportWidth) {
      left = e.clientX - tooltipWidth - 10; // Position to the left of cursor
    }
    // Check if tooltip goes beyond left edge
    if (left < 0) {
      left = 10; // Minimum margin from left
    }
    // Check if tooltip goes beyond top edge
    if (top < 0) {
      top = e.clientY + 20; // Position below cursor instead
    }
    // Check if tooltip goes beyond bottom edge
    if (top + tooltipHeight > viewportHeight) {
      top = viewportHeight - tooltipHeight - 10; // Position at bottom with margin
    }

    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }

  // Mouse enter handler
  element.addEventListener('mouseenter', (e) => {
    const content = getContentCallback();
    if (content) {
      tooltip.style.opacity = '1';
      positionTooltip(e, content);
    }
  });

  // Mouse move handler
  element.addEventListener('mousemove', (e) => {
    const content = getContentCallback();
    if (content) {
      positionTooltip(e, content);
    }
  });

  // Mouse leave handler
  element.addEventListener('mouseleave', () => {
    tooltip.style.opacity = '0';
  });

  element.tooltipSetup = true;
}

function setupTooltipNoData(canvas, chartType) {
  if (canvas.tooltipSetup) return;
  let tooltip = document.getElementById('tooltip_projectDash');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'tooltip_projectDash';
    tooltip.style.cssText = `
      position: fixed;
      background-color: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 14px;
      pointer-events: none;
      z-index: 10000;
      opacity: 0;
      transition: opacity 0.2s;
      white-space: nowrap;
    `;
    document.body.appendChild(tooltip);
  }
  
  function positionTooltip(e, tooltipText) {
    if (!tooltipText) {
      tooltip.style.opacity = '0';
      return;
    }
    tooltip.textContent = tooltipText;
    tooltip.style.opacity = '1';
    tooltip.style.left = '-9999px';
    tooltip.style.top = '-9999px';
    tooltip.style.opacity = '1';
    const tooltipRect = tooltip.getBoundingClientRect();
    const tooltipWidth = tooltipRect.width;
    const tooltipHeight = tooltipRect.height;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    let left = e.clientX + 10;
    let top = e.clientY - 30;
    if (left + tooltipWidth > viewportWidth) left = e.clientX - tooltipWidth - 10;
    if (left < 0) left = 10;
    if (top < 0) top = e.clientY + 20;
    if (top + tooltipHeight > viewportHeight) top = viewportHeight - tooltipHeight - 10;
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }
  
  canvas.addEventListener('mousemove', (e) => {
    let tooltipText = '';
    
    if (chartType === 'workProgressCanvas') {
      tooltipText = `${i18n('noDataFound')} - ${i18n('sectionWork')}`;
    } else if (chartType === 'budgetProgressCanvas') {
      tooltipText = `${i18n('noDataFound')} - ${i18n('Budget')}`;
    } else if (chartType === 'riskProgressCanvas') {
      tooltipText = `${i18n('noDataFound')} - ${i18n('menuRiskManagement')}`;
    } else if (chartType === 'technicalProgressCanvas') {
	  tooltipText = `${i18n('noDataFound')} - ${i18n('menuTechnicalProgress')}`;
	} else if (chartType === 'financialProgressCanvas') {
  	  tooltipText = `${i18n('noDataFound')} - ${i18n('menuInvoice')}`;
  	} else if (chartType === 'ticketProgressCanvas') {
  	  tooltipText = `${i18n('noDataFound')} - ${i18n('sectionTicket')}`;
  	} else if (chartType === 'requirementProgressCanvas') {
	  tooltipText = `${i18n('noDataFound')} - ${i18n('menuRequirementsManagement')}`;
  	} else if (chartType === 'userStoryProgressCanvas') {
  	  tooltipText = `${i18n('noDataFound')} - ${i18n('sectionUserStory')}`;
  	}
    
    positionTooltip(e, tooltipText);
  });
  
  canvas.addEventListener('mouseleave', () => {
    tooltip.style.opacity = '0';
  });
  
  canvas.tooltipSetup = true;
}


//================================================================ PROJECT DETAIL ================================================================
function openProjectDetail(projectId) {
  if (!projectId) {
    console.error('Project ID is required');
    return;
  }
  stockHistory('ProjectDashboard', projectId, 'ProjectDashboardDetail');
  loadContent("projectDashboardDetailMain.php?idProject=" + projectId, "centerDiv");
}

function returnToProjectDashboard() {
  var params = "&objectClass=ProjectDashboard";
  loadMenuBarItem('ProjectDashboard', 'ProjectDashboard', params);
}

function drawProjectDetail() {
  window.top.showWait();

  var container = dojo.byId('divProjectDashboardDetailContent');
  if (!container) {
    console.error('Container divProjectDashboardDetailContent not found');
    window.top.hideWait();
    return;
  }

  // Clean widgets 
  dijit.registry.findWidgets(container).forEach(function(widget) {
    try {
      widget.destroyRecursive();
    } catch(e) {
      console.warn('Error destroying widget:', e);
    }
  });

  container.innerHTML = '';

  if (!document.getElementById('drag-drop-styles')) {
    var style = document.createElement('style');
    style.id = 'drag-drop-styles';
    style.textContent = [
      '.detail-draggable { cursor: grab; transition: opacity .2s, box-shadow .2s; }',
      '.detail-draggable:active { cursor: grabbing; }',
      '.detail-draggable.dragging { opacity: .4; box-shadow: 0 8px 24px rgba(0,0,0,.18); }',
      '.detail-drop-zone.drag-over { outline: 2px dashed #6366f1; outline-offset: 4px; border-radius: 8px; background: rgba(99,102,241,.03); }',
      '.detail-drop-placeholder { height: 6px; background: #6366f1; border-radius: 3px; margin: 4px 0; transition: height .15s; }',
	  '.detail-financial-block[data-zone="zone-left"] .fin-main-row { flex-direction: column; }',
	  '.detail-financial-block[data-zone="zone-left"] .fin-charts-col { flex: 1 1 100%; }',
	  '.detail-financial-block[data-zone="zone-left"] .fin-chart-item { flex: 1 1 100%; }',
	  '.detail-financial-block[data-zone="zone-left"] .fin-table-col { flex: 1 1 100%; max-height: 200px; overflow-y: auto; }'
    ].join('');
    document.head.appendChild(style);
  }
  
  var jsonData = dojo.byId('projectDashboardDetailJsonData');
  if (!jsonData || !jsonData.innerHTML || jsonData.innerHTML.trim() === '') {
    container.innerHTML = '<div style="padding:20px;color:red;">ERROR: No project data found</div>';
    window.top.hideWait();
    return;
  }

  // Data JSON
  var projectData;
  try {
    projectData = JSON.parse(jsonData.innerHTML);
  } catch(e) {
    console.error('Error parsing project data:', e);
    console.error('JSON content:', jsonData.innerHTML);
    container.innerHTML = '<div style="padding:20px;color:red;">ERROR: Invalid project data</div>';
    window.top.hideWait();
    return;
  }

  if (projectData.error) {
    container.innerHTML = '<div style="padding:20px;color:red;">' + projectData.error + '</div>';
    window.top.hideWait();
    return;
  }

  formatProjectDashboardDisplayDates(projectData);
  window.currentProjectData = projectData;
  var showObjectives = getDetailParameter('objectivesDetail');
  var showWeather = getDetailParameter('weatherDetail');
  var showResource = getDetailParameter('resourceDetail');
  var showMilestone = getDetailParameter('milestoneDetail');
  var showFinancial = getDetailParameter('financialDetail');
  //var showBudget = getDetailParameter('budgetDetail');
  var showRevenue = getDetailParameter('revenueDetail');
  var showRisk = getDetailParameter('riskDetail');
  var showOpportunity = getDetailParameter('opportunityDetail');
  var showBurndown = getDetailParameter('burndownDetail');
  var showFortyFiveDegree = getDetailParameter('fortyFiveDegreeDetail');
  var showSCurve = getDetailParameter('sCurveDetail');
  var showRaci = getDetailParameter('raciDetail');
  
  var html = '';

  // Main container
  html += '<div class="project-detail-container" id="project_'+projectData.id+'" data-project-color="' + projectData.color + '" style="display:flex; flex-direction:column; gap:24px;">';
   
  html += '<div style="display:flex; gap:16px;">';
  
  // ================================================================  LEFT
  html += '<div  id="zone-left" class="detail-drop-zone" style="flex: 0 0 33%; min-width: 0; display: flex; flex-direction: column; gap: 16px;">';
  //    Bloc 1/3 - 1
  html += '<div class="detail-block-small" style="background:white;border-radius:8px;padding:20px 20px 10px 20px; position:relative; min-width:0;">';
  // Bloc Photo + Infos
  html += '  <div class="detail-photo-section" style="display: flex; gap: 20px; margin-bottom: 20px;">';
  // Photo + dates
  html += '  <div class="detail-photo-dates" style="display: flex; gap: 10px; width:33%;flex-direction:column;">'; 
  if (projectData.photo) {
    html += '<div class="detail-photo" style="position:relative;padding-top:100%;border-radius:8px;overflow:hidden;">';
    html += '  <img src="' + projectData.photo + '" style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;border-radius:8px;" alt="Project Image">';
    html += '  <div id="addAttachementProjectPic_'+projectData.id+'" class="project-photo-btn" title="'+i18n('removeAttachementProjectPic')+'" onclick="event.stopPropagation(); removeAttachmentWithConfirm(this, '+projectData.idphoto+', '+projectData.id+');">';
    html += '    <div class="iconRemove16 imageColorNewGui iconRemove iconSize16"></div>';
    html += '  </div>';
    html += '</div>';
  } else {
    var bgStyle = projectData.color ? 'background:linear-gradient(135deg, ' + projectData.color + ' 0%, #e9ecef 100%);' : 'background:linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);';
    html += '<div class="detail-photo" style="position:relative;padding-top:100%;border-radius:8px;overflow:hidden;'+bgStyle+'">';
    html += '  <div id="addAttachementProjectPic_'+projectData.id+'" class="project-photo-btn" title="'+i18n('addAttachementProjectPic')+'" onclick="event.stopPropagation(); addAttachmentWithUpdate(this,\'Project\','+projectData.id+',\'profilePic\');">';
    html += '    <div class="iconAdd16 imageColorNewGui iconAdd iconSize16"></div>';
    html += '  </div>';
    html += '</div>';
  }
  // Dates (grid2x3)
  html += '  <div style="padding-top:5px;width:33%;">'; 
  html += '    <div style="display:flex;gap:4px;">';
  var startDates = [
    { value: projectData.validatedstartdate, label: i18n('colValidatedStartDate'), color: projectData.colorvalidatedstart },
    { value: projectData.plannedstartdate, label: i18n('colPlannedStartDate'), color: projectData.colorplannedstart },
    { value: projectData.realstartdate, label: i18n('colRealStartDate'), color: projectData.colorrealstart }
  ];
  var endDates = [
    { value: projectData.validatedenddate, label: i18n('colValidatedEndDate'), color: projectData.colorvalidatedend },
    { value: projectData.plannedenddate, label: i18n('colPlannedEndDate'), color: projectData.colorplannedend },
    { value: projectData.realenddate, label: i18n('colRealEndDate'), color: projectData.colorrealenddate }
  ];
  html += '  <div style="flex:1;">';
  html += '    <div style="text-align:center;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9ca3af;margin-bottom:6px;">';
  html +=          i18n('datesStartDashboard');
  html += '    </div>';
  // Start dates
  html += '  <div style="display:flex;flex-direction:column;gap:8px;flex:1;">';
  startDates.forEach(function(dateInfo, index) {
    var isEmpty = !dateInfo.value || dateInfo.value === '—';
    var displayValue = isEmpty ? '-' : dateInfo.value;
    var backgroundColor = '';
    var textColor = 'color:#666;';
    if (!isEmpty && dateInfo.color) {
      if (dateInfo.color.indexOf('gradient') !== -1) backgroundColor = 'background:' + dateInfo.color + ';';
      else backgroundColor = 'background-color:' + dateInfo.color + ';';
      textColor = 'color:' + getForeColor(dateInfo.color) + ';';
    }
	var borderStyle = '';
	if (isEmpty){
	  backgroundColor = 'background-color:#f0f0f0;';
	  textColor = 'color:#ccc;';
	}
	if (backgroundColor == 'background-color:#FFFFFF;'|| !backgroundColor )  borderStyle = 'border: 1px solid #ccc;';
	html += '<div class="date-row date-start' + (isEmpty ? ' no-date' : '') + '" ';
  	html += 'id="startDate_' + projectData.id + '_' + index + '" ';
	html += 'data-date-label="' + dateInfo.label + '" ';
	html += 'data-date-value="' + displayValue + '" ';
	html += 'style="display:flex;align-items:center;justify-content:center;' 
	      + backgroundColor + textColor + borderStyle + '">';
	html += displayValue;
	html += '</div>';
  });
  html += '  </div>';
  html += '  </div>';
  
  html += '  <div style="flex:1;">';
  html += '    <div style="text-align:center;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9ca3af;margin-bottom:6px;">';
  html +=          i18n('datesEndDashboard');
  html += '    </div>';
  // End Dates
  html += '  <div style="display:flex;flex-direction:column;gap:8px;flex:1;">';
  endDates.forEach(function(dateInfo, index) {
    var isEmpty = !dateInfo.value || dateInfo.value === '—';
    var displayValue = isEmpty ? '-' : dateInfo.value;
    var backgroundColor = '';
    var textColor = 'color:#666;';
    if (!isEmpty && dateInfo.color) {
      if (dateInfo.color.indexOf('gradient') !== -1) backgroundColor = 'background:' + dateInfo.color + ';';
      else backgroundColor = 'background-color:' + dateInfo.color + ';';
      textColor = 'color:' + getForeColor(dateInfo.color) + ';';
    }
	var borderStyle = '';
	if (isEmpty){
	  backgroundColor = 'background-color:#f0f0f0;';
	  textColor = 'color:#ccc;';
	}
	if (backgroundColor == 'background-color:#FFFFFF;' || !backgroundColor)  borderStyle = 'border: 1px solid #ccc;';
	html += '<div class="date-row date-end' + (isEmpty ? ' no-date' : '') + '" ';
 	html += 'id="endDate_' + projectData.id + '_' + index + '" ';
	html += 'data-date-label="' + dateInfo.label + '" ';
	html += 'data-date-value="' + displayValue + '" ';
	html += 'style="display:flex;align-items:center;justify-content:center;' 
	      + backgroundColor + textColor + borderStyle + '">';
	html += displayValue;
	html += '</div>';
  });
  html += '  </div>';
  html += '  </div>';
  html += '  </div>';
  html += '  </div>';
  html += '  </div>'; 
  // Title + Type + Description
  html += '    <div style="flex: 1; width: 66%;display: flex; flex-direction: column; gap: 8px;">';
  // Title
  html += '<div class="tile-header-left" style="display:flex;align-items:center;gap:6px;cursor: pointer;" onclick="top.gotoElement(\'Project\','+projectData.id+');">';
  html += '  <div class="project-color-square-detail" style="width:20px; height:20px;border-radius: 5px; background-color:' + projectData.color + '"></div>';
  html += '  <h3 class="project-title" style="font-size:16px;font-weight:600;">' + projectData.name + '</h3>';
  html += '</div>';
  // Type de projet
  if (projectData.projecttype && projectData.projecttype.name) {
    html += '      <div style="font-size:13px;color:#666;margin-left:26px;padding-bottom:10px;">';
    html += '        <span>' + htmlEncode(projectData.projecttype.name) + '</span>';
    html += '      </div>';
  }
  // Description
  if (projectData.description) {
	html += '  <div style="padding:12px;background:#f8f9fa;border-radius:6px;height:stretch;min-width:0;">';
	html += '    <div style="font-size:12px;font-weight:600;color:#666;margin-bottom:6px;">' + i18n('colDescription').charAt(0).toUpperCase() + i18n('colDescription').slice(1) + ' : </div>';
	html += '    <div style="font-size:13px;color:#333;line-height:1.5;max-height:164px;overflow-y:auto;overflow-x:auto;width:100%;">';
	html += '      <div class="rich-content-wrapper" style="display:inline-block;min-width:100%;">' + projectData.description + '</div>';
	html += '    </div>';
	html += '  </div>';
  } else {
    html += '  <div style="margin-bottom:15px;padding:12px;background:#f8f9fa;border-radius:6px;">';
    html += '    <div style="font-size:12px;font-weight:600;color:#666;margin-bottom:6px;">' + i18n('colDescription').charAt(0).toUpperCase() + i18n('colDescription').slice(1) + ' : ' +'</div>';
    html += '    <div style="font-size:13px;color:#333;line-height:1.5;overflow-x:auto;">' + i18n('undefinedValue') + '</div>';
    html += '  </div>';
  }
  html += '    </div>';
  html += '  </div>';
  html += '  <div style="display:flex;gap:10px;margin-top:15px;border-top:1px solid #e0e0e0;padding-top:5px;">';
  // Goto Project
  html += '    <button class="detail-item" style="flex:1;" title="'+i18n('kanbanGotoItem',new Array(projectData.id, projectData.id))+'" onclick="event.stopPropagation();top.gotoElement(\'Project\','+projectData.id+')">';
  html += '      <div class="iconGoto24 iconGoto iconSize24 imageColorNewGui"></div>';
  html += '    </button>';
  // Search Planning
  html += '    <button class="detail-item" style="flex:1;" title="'+i18n('buttonSearch')+'" onclick="event.stopPropagation();top.directSelectProject(\'Project\','+projectData.id+',false,true);">';
  html += '      <div class="iconButtonSearchPlanning24 iconButtonSearchPlanning iconSize24 imageColorNewGui"></div>';
  html += '    </button>';
  // Goto WorkPlan
  html += '    <button class="detail-item" style="flex:1;" title="'+i18n('gotoWorkPlan')+'" onclick="event.stopPropagation();setSelectedProject(\''+projectData.id+'\',\''+htmlEncode(projectData.name)+'\',\'selectedProject\');gotoElement(\'WorkPlan\',null,false,null,\'workPlan\')">';
  html += '      <div class="iconPlannedWorkManual iconSize24 imageColorNewGui"></div>';
  html += '    </button>';    
  // Hyperlinks
  if (projectData.attachments && projectData.attachments.length > 0) {
    html += '    <div style="position:relative;flex:1;" id="attContainer-' + projectData.id + '">';
    html += '      <button class="detail-item" style="width:100%;" title="' + i18n('sectionAttachment') + '" onclick="event.stopPropagation();toggleAttachmentPopover(' + projectData.id + ');">';
    html += '        <div class="iconButtonDownload24 imageColorNewGui iconButtonDownload iconSize24"></div>';
    html += '      </button>';
    // Popover
    html += '      <div id="attPopover-' + projectData.id + '" style="display:none;position:absolute;bottom:calc(100% + 8px);left:0;min-width:260px;max-width:360px;background:#fff;border:1px solid #e5e7eb;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,0.12);z-index:9999;overflow:hidden;">';
    html += '        <div style="padding:10px 14px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#6b7280;border-bottom:1px solid #f3f4f6;">';
    html +=            i18n('sectionAttachment');
    html += '        </div>';
    html += '        <div style="max-height:240px;overflow-y:auto;">';
	projectData.attachments.forEach(function(att) {
	  var displayName = att.filename || att.link || 'attachment';
	  var target = att.islink ? '#' : 'printFrame';
      html += '<div style="display:flex;align-items:center;gap:10px;padding:8px 14px; cursor:pointer;transition:background .15s;border-bottom:1px solid #f9fafb;" onmouseover="this.style.background=\'#f9fafb\'" onmouseout="this.style.background=\'white\'" ';
      html += '     onclick="event.stopPropagation();window.open(\'' + att.downloadurl + '\',\'' + target + '\');">';
      html += '  <img src="' + att.thumburl + '"  onerror="this.src=\'../view/img/mime/bin.png\'" style="width:25px;height:25px;object-fit:cover;border-radius:3px;flex-shrink:0;" />';
      html += '  <span style="font-size:12px;color:#374151;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:280px;" title="' + htmlEncode(displayName) + '">';
      html +=      htmlEncode(displayName);
      html += '  </span>';
      html += '</div>';
    });
    html += '        </div>';
    html += '      </div>';
    html += '    </div>';
  }
  html += '  </div>';
  html += '  </div>';// bloc 1/3-1
  
  // Bloc 1/3 - 2 Objectives
  var objectivesDisplay = showObjectives ? 'block' : 'none';
  html += '  <div class="detail-block-small detail-objectives-block detail-draggable" draggable="true" data-section="objectivesDetail" style="background:white;border-radius:8px;min-width:0;display:' + objectivesDisplay + '">';
  html += buildBlockHeader('colObjectives');
  if (projectData.objectives) {
	html += '    <div style="font-size:13px;color:#555;line-height:1.6;max-height:350px;overflow-y:auto;overflow-x:auto;width:100%;">';
	html += '      <div class="rich-content-wrapper" style="display:inline-block;min-width:100%;">' + projectData.objectives + '</div>';
    html += '    </div>';
  } else {
    html += '    <div style="font-size:13px;color:#aaa;font-style:italic;">' + i18n('undefinedValue') + '</div>';
  }
  html += '  </div>';//Bloc 1/3 - 2 
  
  // Bloc 1/3 - 3 Weather
  var weatherDisplay = showWeather ? 'block' : 'none';
  html += ' <div class="detail-block-small detail-weather-block detail-draggable" draggable="true" data-section="weatherDetail" style="background:white;border-radius:8px;padding:10px 20px; display:' + weatherDisplay + ';">';
  html += buildBlockHeader('weather');
  html += '   <div style="display:flex;gap:20px;justify-content:space-around;">';
  // Weather
  html += '     <div style="flex:1;text-align:center;">';
  html += '       <div style="font-size:12px;color:#666;font-weight:500;margin-bottom:8px;">' + i18n('colIdHealth').charAt(0).toUpperCase() + i18n('colIdHealth').slice(1) + '</div>';
  if (projectData.weather && projectData.weather.icon) {
      html += '       <div id="weather-detail-' + projectData.id + '" data-weather-name="' + (projectData.weather.name || '') + '" style="width:48px;height:48px;margin:0 auto;display:flex;align-items:center;justify-content:center;cursor:pointer;">';
      html += '         <img src="icons/' + projectData.weather.icon + '" style="width:48px;height:48px;" />';
      html += '       </div>';
  } else if (projectData.weather && projectData.weather.color) {
      html += '       <div id="weather-detail-' + projectData.id + '" data-weather-name="' + (projectData.weather.name || '') + '" style="width:48px;height:48px;margin:0 auto;border-radius:50%;background:' + projectData.weather.color + ';cursor:pointer;"></div>';
  } else {
      html += '       <div id="weather-detail-' + projectData.id + '" data-weather-undefined="true" style="width:48px;height:48px;margin:0 auto;display:flex;align-items:center;justify-content:center;cursor:pointer;">';
      html += '         <span style="font-size:24px;color:#999;">-</span>';
      html += '       </div>';
  }
  html += '     </div>';
  // Quality
  html += '     <div style="flex:1;text-align:center;">';
  html += '       <div style="font-size:12px;color:#666;font-weight:500;margin-bottom:8px;">' + i18n('colIdQuality').charAt(0).toUpperCase() + i18n('colIdQuality').slice(1) + '</div>';
  if (projectData.quality && projectData.quality.icon) {
      html += '       <div id="quality-detail-' + projectData.id + '" data-quality-name="' + (projectData.quality.name || '') + '" style="width:48px;height:48px;margin:0 auto;display:flex;align-items:center;justify-content:center;cursor:pointer;">';
      html += '         <img src="icons/' + projectData.quality.icon + '" style="width:48px;height:48px;" />';
      html += '       </div>';
  } else if (projectData.quality && projectData.quality.color) {
      html += '       <div id="quality-detail-' + projectData.id + '" data-quality-name="' + (projectData.quality.name || '') + '" style="width:48px;height:48px;margin:0 auto;border-radius:50%;background:' + projectData.quality.color + ';cursor:pointer;"></div>';
  } else {
      html += '       <div id="quality-detail-' + projectData.id + '" data-quality-undefined="true" style="width:48px;height:48px;margin:0 auto;display:flex;align-items:center;justify-content:center;cursor:pointer;">';
      html += '         <span style="font-size:24px;color:#999;">-</span>';
      html += '       </div>';
  }
  html += '     </div>';
  // Trend
  html += '     <div style="flex:1;text-align:center;">';
  html += '       <div style="font-size:12px;color:#666;font-weight:500;margin-bottom:8px;">' + i18n('colIdTrend').charAt(0).toUpperCase() + i18n('colIdTrend').slice(1)+ '</div>';
  if (projectData.trend && projectData.trend.icon) {
      html += '       <div id="trend-detail-' + projectData.id + '" data-trend-name="' + (projectData.trend.name || '') + '" style="width:48px;height:48px;margin:0 auto;display:flex;align-items:center;justify-content:center;cursor:pointer;">';
      html += '         <img src="icons/' + projectData.trend.icon + '" style="width:48px;height:48px;" />';
      html += '       </div>';
  } else if (projectData.trend && projectData.trend.color) {
      html += '       <div id="trend-detail-' + projectData.id + '" data-trend-name="' + (projectData.trend.name || '') + '" style="width:48px;height:48px;margin:0 auto;border-radius:50%;background:' + projectData.trend.color + ';cursor:pointer;"></div>';
  } else {
      html += '       <div id="trend-detail-' + projectData.id + '" data-trend-undefined="true" style="width:48px;height:48px;margin:0 auto;display:flex;align-items:center;justify-content:center;cursor:pointer;">';
      html += '         <span style="font-size:24px;color:#999;">-</span>';
      html += '       </div>';
  }
  html += '     </div>';
  html += '   </div>';
  html += ' </div>'; //Bloc 1/3 - 3 
  
  
  // Bloc 2/3 - 4 Resources
  var resourceDisplay = showResource ? 'block' : 'none';
  html += '<div class="detail-block-small detail-resource-block detail-draggable" draggable="true" data-section="resourceDetail" style="background:white;border-radius:8px;padding:10px 20px 20px 20px; display:' + resourceDisplay + ';">';
  html += buildBlockHeader('tabResources');
  // Manager
  html += '  <div style="font-size:14px;font-weight:500;margin-bottom:10px;color:var(--color-dark);">' + i18n('colManager').charAt(0).toUpperCase() + i18n('colManager').slice(1) + ' : </div>';
  html += '  <div class="tile-manager-left" style="display:flex;align-items:center;gap:6px;margin-left: 20px;">';
  var hasManager = projectData.manager && projectData.manager.name;
  if (hasManager) {
    if (projectData.manager.isfile) {
      html += '    <img id="responsibleManager" valueuser="' + htmlDecode(projectData.manager.name) + '" style="border-radius:5px;height:20px;width:20px;" src="' + htmlDecode(projectData.manager.file) + '" />';
    } else {
      var arrayColors = ['#1abc9c','#2ecc71','#3498db','#9b59b6','#34495e','#16a085','#27ae60','#2980b9','#8e44ad','#2c3e50'];
      var keyColor = projectData.manager.id % arrayColors.length;
      var bgColor = arrayColors[keyColor];
      html += '    <span style="color:#fff;background-color:' + bgColor + ';font-size:15px;border-radius:5px;text-align:center;height:20px;width:20px;" id="responsibleManager">' + htmlDecode(projectData.manager.file) + '</span>';
    }
    html += '    <span class="manager-name" style="font-size:13px;color:#333;">';
    html += htmlDecode(projectData.manager.namemanager) + '</span>';
  } else {
    html += '    <span style="color:#ccc;height:20px;width:20px;">-</span>';
    html += '    <span style="color:#ccc;font-size:13px;">' + i18n('undefinedValue') + '</span>';
  }
  html += '  </div>';
  // Team
  html += '  <div style="font-size:14px;font-weight:500;color:#333;margin-bottom:10px;margin-top:20px;color:var(--color-dark);">' + i18n('tabAllocation') + ' : </div>';
  if (projectData.resources && projectData.resources.length > 0) {
    html += '  <div style="display:flex;flex-direction:column;gap:8px;margin-left: 20px;max-height:150px;overflow-x:auto;">';
    projectData.resources.forEach(function(resource) {
      html += '    <div class="tile-manager-left" style="display:flex;align-items:center;gap:6px;">';
      if (resource.isfile) {
        html += '      <img id="resource' + resource.id + '" valueuser="' + htmlEncode(resource.name) + '" style="border-radius:5px;height:20px;width:20px;" src="' + htmlDecode(resource.file) + '" />';
      } else {
        var arrayColors = ['#1abc9c','#2ecc71','#3498db','#9b59b6','#34495e','#16a085','#27ae60','#2980b9','#8e44ad','#2c3e50'];
        var keyColor = resource.id % arrayColors.length;
        var bgColor = arrayColors[keyColor];       
        html += '      <span style="color:#fff;background-color:' + bgColor + ';font-size:15px;border-radius:5px;text-align:center;height:20px;width:20px;" id="resource' + resource.id + '">' + htmlDecode(resource.file) + '</span>';
      } 
      html += '      <div style="display:flex;flex-direction:column;">';
      html += '        <div class="resource-name" style="font-size:13px;color:#333;">' + htmlEncode(resource.name) ;
      if (resource.nameprofile) {
        html += '        <span style="font-size:11px;color:#666;"> - '+ i18n(htmlEncode(resource.nameprofile)) + '</span>';
      }
	  html += '      </div>';
      html += '      </div>';
      
      html += '    </div>';
    });
    html += '  </div>';
  } else {
    html += '  <div style="display:flex;align-items:center;gap:6px;">';
    html += '    <span style="color:#ccc;height:20px;width:20px;">-</span>';
    html += '    <span style="color:#ccc;font-size:13px;">' + i18n('undefinedValue') + '</span>';
    html += '  </div>';
  }
  html += '</div>'; //bloc2/3-4
  
  html += '</div>';//LEFT

  // ========================================================== RIGHT 
  html += '<div id="zone-right" class="detail-drop-zone" style="flex: 0 0 66%; display: flex; flex-direction: column; gap: 16px;">';
  
  // Bloc 2/3 - 1 Milestone
  var milestoneDisplay = showMilestone ? 'block' : 'none';
  html += '<div class="detail-milestone-block detail-draggable" draggable="true" data-section="milestoneDetail" style="background:white;border-radius:8px;min-width:0padding:20px; display:' + milestoneDisplay + ';">';
  html += buildBlockHeader('menuMilestone');
  // Graphics
  html += '  <div style="display:flex;gap:20px;align-items:stretch;min-height:180px;">';
  // Progress Chart
  html += '    <div style="flex:0 0 20%;display:flex;flex-direction:column;align-items:center;justify-content:center;border-right:1px solid #e0e0e0;padding-right:20px;">';
  html += '      <canvas id="detailWorkProgress-' + projectData.id + '" width="180" height="180"></canvas>';
  html += '    </div>';
  // Timeline
  html += '    <div style="flex:1;display:flex;align-items:center;min-width:0;">';
  html += '      <canvas id="timeline-detail-' + projectData.id + '" data-view="detail"></canvas>';
  html += '    </div>';
  html += '  </div>';
  // MILESTONE TABLE
  html += '  <div style="margin-top:24px;">';
  html += '    <div style="border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#ffffff;box-shadow:0 4px 20px rgba(0,0,0,0.04);">';
  html += '      <div style="max-height:300px; overflow:auto;">';
  html += '        <table style="width:100%;border-collapse:separate;border-spacing:0;font-family:Inter,sans-serif;">';
  // HEADER
  html += '          <thead>';
  html += '            <tr style="background:#f9fafb;">';
  html += '              <th style="padding:12px 14px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;width:180px;max-width:180px;">';
  html +=                  i18n('ListOfMilestone');
  html += '              </th>';
  html += '              <th style="padding:12px 14px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;">';
  html +=                  i18n('MilestoneType').charAt(0).toUpperCase() + i18n('MilestoneType').slice(1);
  html += '              </th>';
  html += '              <th style="padding:12px 14px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;">';
  html +=                  i18n('Planning').charAt(0).toUpperCase() + i18n('Planning').slice(1);
  html += '              </th>';
  html += '              <th style="padding:12px 14px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;">';
  html +=                  i18n('colValidatedDueDate').charAt(0).toUpperCase() + i18n('colValidatedDueDate').slice(1);
  html += '              </th>';
  html += '              <th style="padding:12px 14px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;">';
  html +=                  i18n('colPlannedDueDate').charAt(0).toUpperCase() + i18n('colPlannedDueDate').slice(1);
  html += '              </th>';
  html += '              <th style="padding:12px 14px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;">';
  html +=                  i18n('colRealDueDate').charAt(0).toUpperCase() + i18n('colRealDueDate').slice(1);
  html += '              </th>';
  html += '              <th style="padding:12px 14px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;">';
  html +=                  i18n('colStatus');
  html += '              </th>';
  html += '            </tr>';
  html += '          </thead>';
  // BODY
  html += '          <tbody>';
  if (projectData.milestones && projectData.milestones.length > 0) {
    projectData.milestones.forEach(function(milestone) {
		html += '      <tr ';
		html += '        onclick="gotoElement(\'Milestone\', \'' + milestone.id + '\')" ';
		html += '        style="cursor:pointer;transition:all .15s ease;border-bottom:1px solid #f3f4f6;" ';
		html += '        onmouseover="this.style.background=\'#f9fafb\'" ';
		html += '        onmouseout="this.style.background=\'white\'"';
		html += '      >';
		// NAME
		html += '        <td style="padding:11px 14px;">';
		html += '          <div style="display:flex;align-items:center;gap:10px;">';
		html += '            <div style="width:9px;height:9px;border-radius:999px;background:' + milestone.colorstatus + ';flex-shrink:0;box-shadow:0 0 0 1px rgba(0,0,0,0.18);"></div>';
		html += '            <div style="font-size:13px;font-weight:600;color:#374151;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px;" title="' + htmlEncode(milestone.name || '') + '">';
		html +=                (milestone.name || '-');
		html += '            </div>';
		html += '          </div>';
		html += '        </td>';
		// TYPE 
		html += '        <td style="padding:11px 14px;font-size:13px;color:#6b7280;white-space:nowrap;">';
		html +=            (milestone.type || '-');
		html += '        </td>';
		// MODE 
		html += '        <td style="padding:11px 14px;font-size:13px;color:#6b7280;white-space:nowrap;">';
		html +=            (i18n(milestone.mode) || '-');
		html += '        </td>';
		// DATES
		html += '        <td style="padding:11px 14px;font-size:13px;color:#6b7280;white-space:nowrap;">';
		html +=            (milestone.validateddate || '-');
		html += '        </td>';
		html += '        <td style="padding:11px 14px;font-size:13px;color:#6b7280;white-space:nowrap;">';
		html +=            (milestone.plannedenddate || '-');
		html += '        </td>';
		html += '        <td style="padding:11px 14px;font-size:13px;color:#6b7280;white-space:nowrap;">';
		html +=            (milestone.realenddate || '-');
		html += '        </td>';
		// STATUS
		html += '        <td style="padding:11px 14px;">';
		html += '          <div style="display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:' + milestone.colorstatus + ';color:' + getForeColor(milestone.colorstatus) + ';font-size:11px;font-weight:600;white-space:nowrap;box-shadow:0 0 0 1px rgba(0,0,0,0.18);">';
		html +=              milestone.status;
		html += '          </div>';
		html += '        </td>';
		html += '      </tr>';
    });
  } else {
    html += '    <tr>';
    html += '      <td colspan="7" style="padding:56px 24px;text-align:center;color:#9ca3af;font-size:13px;">';
    html +=          i18n('noDataFound');
    html += '      </td>';
    html += '    </tr>';
  }
  html += '          </tbody>';
  html += '        </table>';
  html += '      </div>';
  html += '    </div>';
  html += '  </div>';
  html += '</div>'; // bloc2/3-1
  
  // Bloc 2/3 - 2 Financial
  var financialDisplay = showFinancial ? 'block' : 'none';
  html += '<div class="detail-financial-block detail-draggable" draggable="true" data-section="financialDetail" style="background:white;border-radius:8px;padding:20px;min-width:0;overflow:hidden;display:' + financialDisplay + ';">';
  html += buildBlockHeader('menuFinancial');
  // Strategic Value + Benefit Value
  html += '  <div style="display:flex;gap:16px;margin-bottom:20px;">';
  html += '    <div style="flex:1;padding:16px 18px;border:1px solid #e5e7eb;border-radius:14px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.03);display:flex;align-items:center;justify-content:space-between;">';
  html += '      <div style="display:flex;align-items:center;gap:10px;">';
  html += '        <div style="width:10px;height:10px;border-radius:50%;background:#6366f1;"></div>';
  html += '        <div style="font-size:13px;font-weight:600;color:#374151;">';
  html +=            i18n('colStrategicValue').charAt(0).toUpperCase() + i18n('colStrategicValue').slice(1);
  html += '        </div>';
  html += '      </div>';
  html += '      <div style="font-size:13px;font-weight:700;color:#111827;">';
  html +=          (projectData.strategicvalue !== null && projectData.strategicvalue !== undefined && projectData.strategicvalue !== '')
                   ? numericFormatter(projectData.strategicvalue)
                   : '<span style="color:#d1d5db;">—</span>';
  html += '      </div>';
  html += '    </div>';
  html += '    <div style="flex:1;padding:16px 18px;border:1px solid #e5e7eb;border-radius:14px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.03);display:flex;align-items:center;justify-content:space-between;">';
  html += '      <div style="display:flex;align-items:center;gap:10px;">';
  html += '        <div style="width:10px;height:10px;border-radius:50%;background:#22c55e;"></div>';
  html += '        <div style="font-size:13px;font-weight:600;color:#374151;">';
  html +=            i18n('colBenefitValue').charAt(0).toUpperCase() + i18n('colBenefitValue').slice(1);
  html += '        </div>';
  html += '      </div>';
  html += '      <div style="font-size:13px;font-weight:700;color:#111827;">';
  html +=          (projectData.benefitvalue !== null && projectData.benefitvalue !== undefined && projectData.benefitvalue !== '')
                   ? numericFormatter(projectData.benefitvalue)
                   : '<span style="color:#d1d5db;">—</span>';
  html += '      </div>';
  html += '    </div>';
  html += '  </div>';
  
  html += '<div class="fin-main-row" style="display:flex;gap:20px;align-items:stretch;flex-wrap: wrap;">';
  // Progress charts
  html += '<div class="fin-charts-col" style="flex:2;display:flex;gap:16px;flex-wrap: wrap;">';
  // COST
  html += '    <div  class="fin-chart-item" style="flex:1;display:flex;gap:5px;align-items:center;background:#f8f9fa;border-radius:8px;padding:16px;">';
  html += '      <div style="flex:0 0 auto;position:relative;width:130px;height:130px;">';
  html += '        <canvas id="detailCostProgress-' + projectData.id + '" width="130" height="130"></canvas>';
  html += '      </div>';
  html += '      <div style="flex:1;">';
  html += '        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#6b7280;margin-bottom:12px;">';
  html +=            i18n('colCost');
  html += '        </div>';
  html += '        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;">';
  html += '          <span style="font-size:11px;color:#6b7280;font-weight:500;">';
  html +=              i18n('totalAssigned').charAt(0).toUpperCase() + i18n('totalAssigned').slice(1);
  html += '          </span>';
  html += '          <span style="font-size:11px;font-weight:700;color:#374151;">';
  html +=              costFormatter(projectData.totalassignedcost || 0, null, false, true);
  html += '          </span>';
  html += '        </div>';
  html += '        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #f3f4f6;">';
  html += '          <span style="font-size:11px;color:#6b7280;font-weight:500;">';
  html +=              i18n('colTotalReal').charAt(0).toUpperCase() + i18n('colTotalReal').slice(1);
  html += '          </span>';
  html += '          <span style="font-size:11px;font-weight:700;color:#111827;">';
  html +=              costFormatter(projectData.totalvalidatedcost || 0, null, false, true);
  html += '          </span>';
  html += '        </div>';
  html += '      </div>';
  html += '    </div>';
  // Expense
  html += '    <div class="fin-chart-item" style="flex:1;display:flex;gap:5px;align-items:center;background:#f8f9fa;border-radius:8px;padding:16px;">';
  html += '      <div style="flex:0 0 auto;position:relative;width:130px;height:130px;">';
  html += '        <canvas id="detailExpenseProgress-' + projectData.id + '" width="130" height="130"></canvas>';
  html += '      </div>';
  html += '      <div style="flex:1;">';
  html += '        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#6b7280;margin-bottom:12px;">';
  html +=            i18n('menuExpenses');
  html += '        </div>';
  html += '        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #f3f4f6;">';
  html += '          <span style="font-size:11px;color:#6b7280;font-weight:500;">';
  html +=              i18n('colExpenseValidatedAmount').charAt(0).toUpperCase() + i18n('colExpenseValidatedAmount').slice(1);
  html += '          </span>';
  html += '          <span style="font-size:11px;font-weight:700;color:#111827;">';
  html +=              costFormatter(projectData.expensevalidatedamount || 0, null, false, true);
  html += '          </span>';
  html += '        </div>';
  html += '        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;">';
  html += '          <span style="font-size:11px;color:#6b7280;font-weight:500;">';
  html +=              i18n('colExpenseAssignedAmount').charAt(0).toUpperCase() + i18n('colExpenseAssignedAmount').slice(1);
  html += '          </span>';
  html += '          <span style="font-size:11px;font-weight:700;color:#374151;">';
  html +=              costFormatter(projectData.expenseassignedamount || 0, null, false, true);
  html += '          </span>';
  html += '        </div>';
  html += '      </div>';
  html += '  </div>';
  html += '  </div>'; 
  // Table
  html += '<div class="fin-table-col" style="flex:1;min-width:0;border:1px solid #e5e7eb;border-radius:12px;overflow:auto;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,0.04);">';
  html += '    <table style="width:100%;border-collapse:separate;border-spacing:0;font-family:Inter,sans-serif;">';
  // Head
  html += '      <thead>';
  html += '        <tr style="background:#f9fafb;">';
  html += '          <th style="padding:12px 16px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;"></th>';
  html += '          <th style="padding:12px 16px;text-align:right;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#374151;border-bottom:1px solid #e5e7eb;border-left:1px solid #e5e7eb;">' + i18n('colPlanned') + '</th>';
  html += '          <th style="padding:12px 16px;text-align:right;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#374151;border-bottom:1px solid #e5e7eb;border-left:1px solid #e5e7eb;">' + i18n('colReal') + '</th>';
  html += '        </tr>';
  html += '      </thead>';
  html += '      <tbody>';
  // 1 : Resource cost
  html += '        <tr onmouseover="this.style.background=\'#f9fafb\'" onmouseout="this.style.background=\'white\'" style="transition:background .15s;">';
  html += '          <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#374151;border-bottom:1px solid #f3f4f6;">';
  html += '            <div style="display:flex;align-items:center;gap:8px;"><div style=""></div>' + i18n('colResourceCost').charAt(0).toUpperCase() + i18n('colResourceCost').slice(1) + '</div>';
  html += '          </td>';
  html += '          <td style="padding:12px 16px;text-align:right;font-size:13px;color:#6b7280;border-bottom:1px solid #f3f4f6;border-left:1px solid #f3f4f6;">';
  html +=              costFormatter(projectData.plannedresourcecost || 0, null, false, true);
  html += '          </td>';
  html += '          <td style="padding:12px 16px;text-align:right;font-size:13px;font-weight:600;color:#374151;border-bottom:1px solid #f3f4f6;border-left:1px solid #f3f4f6;">';
  html +=              costFormatter(projectData.realresourcecost || 0, null, false, true);
  html += '          </td>';
  html += '        </tr>';
  // 2 : Project expense
  html += '        <tr onmouseover="this.style.background=\'#f9fafb\'" onmouseout="this.style.background=\'white\'" style="transition:background .15s;">';
  html += '          <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#374151;border-bottom:1px solid #f3f4f6;">';
  html += '            <div style="display:flex;align-items:center;gap:8px;"><div style=""></div>' + i18n('colIdProjectExpense').charAt(0).toUpperCase() + i18n('colIdProjectExpense').slice(1) + '</div>';
  html += '          </td>';
  html += '          <td style="padding:12px 16px;text-align:right;font-size:13px;color:#6b7280;border-bottom:1px solid #f3f4f6;border-left:1px solid #f3f4f6;">';
  html +=              costFormatter(projectData.plannedprojectexpense || 0, null, false, true);
  html += '          </td>';
  html += '          <td style="padding:12px 16px;text-align:right;font-size:13px;font-weight:600;color:#374151;border-bottom:1px solid #f3f4f6;border-left:1px solid #f3f4f6;">';
  html +=              costFormatter(projectData.realprojectexpense || 0, null, false, true);
  html += '          </td>';
  html += '        </tr>';
  // 3 : Activity expense
  html += '        <tr onmouseover="this.style.background=\'#f9fafb\'" onmouseout="this.style.background=\'white\'" style="transition:background .15s;">';
  html += '          <td style="padding:12px 16px;font-size:13px;font-weight:600;color:#374151;">';
  html += '            <div style="display:flex;align-items:center;gap:8px;"><div style=""></div>' + i18n('ActivityExpense') + '</div>';
  html += '          </td>';
  html += '          <td style="padding:12px 16px;text-align:right;font-size:13px;color:#6b7280;border-left:1px solid #f3f4f6;">';
  html +=              costFormatter(projectData.plannedactivitycost || 0, null, false, true);
  html += '          </td>';
  html += '          <td style="padding:12px 16px;text-align:right;font-size:13px;font-weight:600;color:#374151;border-left:1px solid #f3f4f6;">';
  html +=              costFormatter(projectData.realactivitycost || 0, null, false, true);
  html += '          </td>';
  html += '        </tr>';
  html += '      </tbody>';
  html += '    </table>';
  html += '  </div>';
  html += '</div>';
  html += '</div>'; // fin detail-financial-block
  
//  // Bloc 2/3 - 3 budget
//  var budgetDisplay = showBudget ? 'block' : 'none';
//  html += '<div class="detail-budget-block" style="background:white;border-radius:8px;padding:20px; display:' + budgetDisplay + ';">';
//  html += '  <div style="font-size:14px;font-weight:600;color:#333;margin-bottom:15px;color:var(--color-dark);">' + i18n('Budget') + '</div>';
//  html += '  <div style="border-top: 1px solid #e0e0e0; margin-bottom: 12px;"></div>';
//  html += '</div>'; //bloc2/3-3
  
  // Bloc 2/3 - 4 revenue
  var revenueDisplay = showRevenue ? 'block' : 'none';
  html += '<div class="detail-revenue-block detail-draggable" draggable="true" data-section="revenueDetail" style="background:white;border-radius:8px;padding:20px; display:' + revenueDisplay + ';">';
  html += buildBlockHeader('sectionRevenue');
  // CA 
  html += '  <div style="display:flex;gap:20px;margin-bottom:20px;align-items:center;">';
  html += '    <div style="flex:0 0 200px;">';
  html += '      <div style="font-size:12px;font-weight:600;color:#666;margin-bottom:8px;">' + i18n('sectionRevenue') + '</div>';
  html += '      <div style="font-size:24px;font-weight:700;color:#333;">' + (projectData.revenue ? costFormatter(projectData.revenue, null, false, true) : '0 €') + '</div>';
  html += '    </div>';
  html += '    <div style="flex:1;">';
  html += '      <div style="font-size:12px;font-weight:600;color:#666;margin-bottom:8px;">'+ i18n('colCommandSum').charAt(0).toUpperCase() + i18n('colCommandSum').slice(1) +'</div>';
  html += '      <select id="commandSelect-' + projectData.id + '" onchange="loadWorkCommands(' + projectData.id + ', this.value);" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;">';
  html += '        <option value="">' + i18n('selectCommand') + '</option>';
  if (projectData.commands && projectData.commands.length > 0) {
    projectData.commands.forEach(function(cmd) {
      html += '          <option value="' + cmd.id + '">' + htmlEncode(cmd.name) + ' (' + costFormatter(cmd.fullAmount, null, false, true) + ')</option>';
    });
  }
  html += '      </select>';
  html += '    </div>';
  html += '  </div>';
  // WordCommands
  html += '<div style="margin-top:24px;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#ffffff;box-shadow:0 4px 20px rgba(0,0,0,0.04);">';
  html += '  <div style="padding:16px 20px;border-bottom:1px solid #eef2f7;background:linear-gradient(to bottom,#ffffff,#fafbfc);display:flex;align-items:center;justify-content:space-between;">';
  html += '    <div style="font-size:15px;font-weight:700;color:#111827;">';
  html +=        i18n('menuWorkCommand');
  html += '    </div>';
  html += '  </div>';
  html += '  <div style="overflow-x:auto;">';
  html += '    <table style="width:100%;border-collapse:separate;border-spacing:0;font-family:Inter,sans-serif;">';
  html += '      <thead>';
  html += '        <tr style="background:#f9fafb;">';
  html += '          <th style="position:sticky;left:0;z-index:2;background:#f9fafb;padding:18px 16px;text-align:left;font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;min-width:240px;">';
  html +=              i18n('colName');
  html += '          </th>';
  html += '          <th colspan="2" style="padding:18px 12px;text-align:center;font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#374151;border-bottom:1px solid #e5e7eb;background:#eef2ff;">';
  html += '            <div style="display:inline-flex;align-items:center;gap:8px;">';
  html += '              <div style="width:8px;height:8px;border-radius:999px;background:#6366f1;"></div>';
  html +=                i18n('colOrdered');
  html += '            </div>';
  html += '          </th>';
  html += '          <th colspan="2" style="padding:18px 12px;text-align:center;font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#374151;border-bottom:1px solid #e5e7eb;background:#ecfeff;">';
  html += '            <div style="display:inline-flex;align-items:center;gap:8px;">';
  html += '              <div style="width:8px;height:8px;border-radius:999px;background:#06b6d4;"></div>';
  html +=                i18n('colRealised');
  html += '            </div>';
  html += '          </th>';
  html += '          <th colspan="2" style="padding:18px 12px;text-align:center;font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#374151;border-bottom:1px solid #e5e7eb;background:#f0fdf4;">';
  html += '            <div style="display:inline-flex;align-items:center;gap:8px;">';
  html += '              <div style="width:8px;height:8px;border-radius:999px;background:#22c55e;"></div>';
  html +=                i18n('colAccepted');
  html += '            </div>';
  html += '          </th>';
  html += '          <th colspan="2" style="padding:18px 12px;text-align:center;font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#374151;border-bottom:1px solid #e5e7eb;background:#fef3c7;">';
  html += '            <div style="display:inline-flex;align-items:center;gap:8px;">';
  html += '              <div style="width:8px;height:8px;border-radius:999px;background:#f59e0b;"></div>';
  html +=                i18n('colBilled');
  html += '            </div>';
  html += '          </th>';
  html += '        </tr>';
  html += '        <tr style="background:white;">';
  html += '          <th style="position:sticky;left:0;z-index:2;background:white;padding:12px 16px;border-bottom:1px solid #e5e7eb;"></th>';
  html += '          <th style="padding:10px 12px;text-align:center;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;border-bottom:1px solid #e5e7eb;">';
  html +=              i18n('colQty');
  html += '          </th>';
  html += '          <th style="padding:10px 12px;text-align:right;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;border-bottom:1px solid #e5e7eb;">';
  html +=              i18n('colAmount');
  html += '          </th>';
  html += '          <th style="padding:10px 12px;text-align:center;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;border-bottom:1px solid #e5e7eb;">';
  html +=              i18n('colQty');
  html += '          </th>';
  html += '          <th style="padding:10px 12px;text-align:right;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;border-bottom:1px solid #e5e7eb;">';
  html +=              i18n('colAmount');
  html += '          </th>';
  html += '          <th style="padding:10px 12px;text-align:center;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;border-bottom:1px solid #e5e7eb;">';
  html +=              i18n('colQty');
  html += '          </th>';
  html += '          <th style="padding:10px 12px;text-align:right;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;border-bottom:1px solid #e5e7eb;">';
  html +=              i18n('colAmount');
  html += '          </th>';
  html += '          <th style="padding:10px 12px;text-align:center;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;border-bottom:1px solid #e5e7eb;">';
  html +=              i18n('colQty');
  html += '          </th>';
  html += '          <th style="padding:10px 12px;text-align:right;font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;border-bottom:1px solid #e5e7eb;">';
  html +=              i18n('colAmount');
  html += '          </th>';
  html += '        </tr>';
  html += '      </thead>';
  html += '      <tbody id="workCommandsTable-' + projectData.id + '">';
  html += '        <tr style="transition:background .2s ease;" onmouseover="this.style.background=\'#fafafa\'" onmouseout="this.style.background=\'white\'">';
  html += '          <td colspan="9" style="padding:48px 24px;text-align:center;">';
  html += '            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;">';
  html += '              <div style="width:56px;height:56px;border-radius:16px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;font-size:24px;">📋</div>';
  html += '              <div>';
  html += '                <div style="margin-top:4px;font-size:12px;color:#9ca3af;">';
  html +=                    i18n('selectCommand');
  html += '                </div>';
  html += '              </div>';
  html += '            </div>';
  html += '          </td>';
  html += '        </tr>';
  html += '      </tbody>';
  html += '    </table>';
  html += '  </div>';
  html += '</div>';
  html += '  </div>'; //bloc2/3-4
  
 var showTornado = getDetailParameter('tornadoDetail');
 html += buildRiskOpportunityBlock(projectData, 'risk', showRisk);
 html += buildRiskOpportunityBlock(projectData, 'opportunity', showOpportunity);
 html += buildTornadoBlock(projectData, showTornado);
 
 // Bloc 2/3 RACI
   var raciDisplay = showRaci ? 'block' : 'none';
   html += '<div class="detail-raci-block detail-draggable" draggable="true" data-section="raciDetail" ';
   html += '     style="background:white;border-radius:8px;padding:20px;min-width:0;overflow:hidden;display:' + raciDisplay + ';">';
   html += buildBlockHeader('raci');
   if (projectData.racihtml && projectData.racihtml.trim() !== '') {
     html += '<div style="overflow-x:auto;">';
     html +=   projectData.racihtml;
     html += '</div>';
   } else {
     html += '<div style="padding:40px;text-align:center;color:#9ca3af;font-size:13px;">' + i18n('noDataFound') + '</div>';
   }
   html += '</div>'; // bloc2/3-5 RACI
 

  html += '</div>'; //droit
  html += '</div>'; // fin LIGNE 1 (1/3 - 2/3)

  
  // ====================== SEC REPPORTS 2 : 1/2 - 1/2
  html += '<div id="zone-reports" class="detail-drop-zone" style="display:grid; grid-template-columns:repeat(2, 1fr); gap:16px;">';
  
  var burndownDisplay = showBurndown ? 'block' : 'none';
  html += '<div class="detail-burndown-block detail-draggable" draggable="true" data-section="burndownDetail" style="background:white;border-radius:8px;padding:20px; display:' + burndownDisplay + ';">';
  html += buildBlockHeader('reportBurndownChart');
  html += '  <div id="burndown-chart-' + projectData.id + '" style="min-height:600px;display:flex;align-items:center;justify-content:center;">';
  html += '    <div class="loading-spinner" style="text-align:center;">';
  html += '      <div style="color:#666;font-size:14px;">' + i18n('loading') + '...</div>';
  html += '    </div>';
  html += '  </div>';
  html += '</div>'; 

  var fortyFiveDegreDisplay = showFortyFiveDegree ? 'block' : 'none';
  html += '<div class="detail-45degree-block detail-draggable" draggable="true" data-section="fortyFiveDegreeDetail" style="background:white;border-radius:8px;padding:20px; display:' + fortyFiveDegreDisplay + ';">';
  html += buildBlockHeader('report45DegreeChart');
  html += '  <div id="fortyFiveDegree-chart-' + projectData.id + '" style="min-height:400px;display:flex;align-items:center;justify-content:center;">';
  html += '    <div class="loading-spinner" style="text-align:center;">';
  html += '      <div style="color:#666;font-size:14px;">' + i18n('loading') + '...</div>';
  html += '    </div>';
  html += '  </div>';
  html += '</div>'; 
  
  var sCurveDisplay = showSCurve ? 'block' : 'none';
  html += '<div class="detail-scurve-block detail-draggable" draggable="true" data-section="sCurveDetail" style="background:white;border-radius:8px;padding:20px; display:' + sCurveDisplay + ';">';
  html += buildBlockHeader('reportSCurveChart');
  html += '  <div id="sCurve-chart-' + projectData.id + '" style="min-height:400px;display:flex;align-items:center;justify-content:center;">';
  html += '    <div class="loading-spinner" style="text-align:center;">';
  html += '      <div style="color:#666;font-size:14px;">' + i18n('loading') + '...</div>';
  html += '    </div>';
  html += '  </div>';
  html += '</div>'; 
  
  html += '</div>'; // End sec Reports

  html += '</div>'; // End project-detail-container

  container.innerHTML = html;
  dojo.parser.parse(container);
  
  restoreSectionOrder();

  setTimeout(function() {

    var workProgressCanvas = document.getElementById('detailWorkProgress-' + projectData.id);
    if (workProgressCanvas) {
      progressChart(workProgressCanvas,projectData.validatedwork || 0,projectData.realwork || 0,projectData.leftwork || 0,projectData.plannedwork || 0,'workProgressCanvas','<div class="iconImputation16 imageColorNewGui iconImputation iconSize16"></div>');
    }
	
	var costProgressCanvas = document.getElementById('detailCostProgress-' + projectData.id);
	if (costProgressCanvas) {
	  progressChart(costProgressCanvas,projectData.totalvalidatedcost || 0,projectData.totalrealcost || 0,projectData.totalleftcost || 0,projectData.totalplannedcost  || 0,'budgetProgressCanvas','<div class="iconExpenses16 imageColorNewGui iconExpenses iconSize16"></div>');
	}

	var expenseProgressCanvas = document.getElementById('detailExpenseProgress-' + projectData.id);
	if (expenseProgressCanvas) {
	  progressChart(expenseProgressCanvas, projectData.expensevalidatedamount || 0,  projectData.expenserealamount || 0, projectData.expenseleftamount || 0, projectData.expenseplannedamount || 0,  'budgetProgressCanvas',   '<div class="iconProjectExpense iconSize16 imageColorNewGui iconSize16"></div>');
	}
	    
	var timelineCanvas = document.getElementById('timeline-detail-' + projectData.id);
	if (timelineCanvas) {
	  var useColorMilestone = getDashboardParameter('colorMilestone');
	  createTimeline('timeline-detail-' + projectData.id, projectData.validatedstartdate, projectData.plannedstartdate, projectData.realstartdate, projectData.validatedenddate, projectData.plannedenddate, projectData.realenddate, projectData.milestones || [], useColorMilestone, getTimelineDateValues(projectData));  
	}
	
	if (projectData.risks        && projectData.risks.length > 0)        drawIndicatorCharts(projectData, 'risk');
	if (projectData.opportunities && projectData.opportunities.length > 0) drawIndicatorCharts(projectData, 'opportunity');
	if ((projectData.risks && projectData.risks.length > 0) || (projectData.opportunities && projectData.opportunities.length > 0)) drawTornadoChart(projectData);
	
	loadBurndownChart(projectData.id); 
	loadFortyFiveDegreeChart(projectData.id);
	loadSCurveChart(projectData.id, projectData.idbaseline);
	
	var weatherElement = document.getElementById('weather-detail-' + projectData.id);
	if (weatherElement) {
	  var isUndefined = weatherElement.getAttribute('data-weather-undefined') === 'true';
	  if (isUndefined) {
	    setupTooltipDashboard(weatherElement, function() {
	      return i18n('colIdHealth') + ' : ' + i18n('undefinedValue');
	    });
	  } else {
	    setupTooltipDashboard(weatherElement, function() {
	      var label = this.getAttribute('data-weather-name');
	      var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
	      return labelBis;
	    }.bind(weatherElement));
	  }
	 }
	  
	 // Quality tooltip
	 var qualityElement = document.getElementById('quality-detail-' + projectData.id);
	 if (qualityElement) {
	   var isUndefined = qualityElement.getAttribute('data-quality-undefined') === 'true';
	   if (isUndefined) {
	     setupTooltipDashboard(qualityElement, function() {
	       return i18n('colIdQuality') + ' : ' + i18n('undefinedValue');
	 	 });
	   } else {
	     setupTooltipDashboard(qualityElement, function() {
	       var label = this.getAttribute('data-quality-name');
	       var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
	       return labelBis;
	     }.bind(qualityElement));
	   }
	 }
	  
	 // Trend tooltip
	 var trendElement = document.getElementById('trend-detail-' + projectData.id);
	 if (trendElement) {
	   var isUndefined = trendElement.getAttribute('data-trend-undefined') === 'true';
	   if (isUndefined) {
	     setupTooltipDashboard(trendElement, function() {
	       return i18n('colIdTrend') + ' : ' + i18n('undefinedValue');
	     });
	   } else {
	     setupTooltipDashboard(trendElement, function() {
	       var label = this.getAttribute('data-trend-name');
	       var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
	       return labelBis;
	     }.bind(trendElement));
	    }
	  }
	  
	  // Date tooltips - Start dates
	  for (var j = 0; j < 3; j++) {
	    var startDateElement = document.getElementById('startDate_' + projectData.id + '_' + j);
	    if (startDateElement) {
	      setupTooltipDashboard(startDateElement, function() {
	        var label = this.getAttribute('data-date-label');
	        var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
	        var value = this.getAttribute('data-date-value');
	        return labelBis + ' : ' + value;
	      }.bind(startDateElement));
	    }
	  }

	  // Date tooltips - End dates
	  for (var j = 0; j < 3; j++) {
	    var endDateElement = document.getElementById('endDate_' + projectData.id + '_' + j);
	    if (endDateElement) {
	      setupTooltipDashboard(endDateElement, function() {
	        var label = this.getAttribute('data-date-label');
	        var labelBis = label.charAt(0).toUpperCase() + label.slice(1);
	        var value = this.getAttribute('data-date-value');
	        return labelBis + ' : ' + value;
	      }.bind(endDateElement));
	    }
	  }
	  
	  initDragAndDrop();
	  
  }, 100);
  
  initializeLayoutRecordingDetail();
  window.top.hideWait();
}


function drawRiskCharts(projectData) {
  // ===== PIE CHART =====
  var riskTypeCanvas = document.getElementById('riskType-' + projectData.id);
  if (riskTypeCanvas) {
    var riskTypeCount = {};
    var riskTypeColors = {};
    
    projectData.risks.forEach(function(risk) {
      var type = risk.risktype || i18n('undefinedValue');
      riskTypeCount[type] = (riskTypeCount[type] || 0) + 1;
      if (!riskTypeColors[type]) {
        riskTypeColors[type] = getColorFromHash(type);
      }
    });
    
    var typeLabels = Object.keys(riskTypeCount);
    var typeData = typeLabels.map(function(label) { return riskTypeCount[label]; });
    var typeColors = typeLabels.map(function(label) { return riskTypeColors[label]; });
    
    var riskTypeCtx = riskTypeCanvas.getContext('2d');
    new Chart(riskTypeCtx, {
      type: 'doughnut',
      data: {
        labels: typeLabels,
        datasets: [{
          data: typeData,
          backgroundColor: typeColors,
          borderColor: '#fff',
          borderWidth: typeData.length === 1 ? 0 : 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              font: { size: 11 },
              padding: 10
            }
          },
          tooltip: {
            callbacks: {
			  label: function(context) {
				var count = context.parsed;
				var label = count === 1 ? i18n('Risk').charAt(0).toLowerCase() + i18n('Risk').slice(1) : i18n('menuRisk').charAt(0).toLowerCase() + i18n('menuRisk').slice(1);
				return context.label + ': ' + count + ' ' + label;
			  }
            }
          }
        },
        cutout: typeData.length === 1 ? '0%' : '50%'
      }
    });
  }
  
  // ===== BAR CHART =====
  var indicatorsCanvas = document.getElementById('riskIndicators-' + projectData.id);
  if (indicatorsCanvas) {
    var severityData = {};
    var likelihoodData = {};
    var criticalityData = {};
    
    projectData.risks.forEach(function(risk) {
      var sev = risk.severityname || 'Indéfini';
      var lik = risk.likelihoodname || 'Indéfini';
      var crit = risk.criticalityname || 'Indéfini';
      
      severityData[sev] = severityData[sev] || { count: 0, color: risk.severitycolor || '#999' };
      severityData[sev].count++;
      
      likelihoodData[lik] = likelihoodData[lik] || { count: 0, color: risk.likelihoodcolor || '#999' };
      likelihoodData[lik].count++;
      
      criticalityData[crit] = criticalityData[crit] || { count: 0, color: risk.criticalitycolor || '#999' };
      criticalityData[crit].count++;
    });
    
    var severityDatasets = Object.keys(severityData).map(function(label) {
      return {
        label: label,
        data: [severityData[label].count],
        backgroundColor: severityData[label].color
      };
    });
    
    var likelihoodDatasets = Object.keys(likelihoodData).map(function(label) {
      return {
        label: label,
        data: [likelihoodData[label].count],
        backgroundColor: likelihoodData[label].color
      };
    });
    
    var criticalityDatasets = Object.keys(criticalityData).map(function(label) {
      return {
        label: label,
        data: [criticalityData[label].count],
        backgroundColor: criticalityData[label].color
      };
    });
    
    var indicatorsCtx = indicatorsCanvas.getContext('2d');
    new Chart(indicatorsCtx, {
      type: 'bar',
      data: {
        labels: [i18n('colIdSeverity'), i18n('colIdLikelihood'), i18n('colIdCriticality')],
        datasets: [
          ...severityDatasets.map(function(ds, i) { 
            return { ...ds, data: [ds.data[0], 0, 0] }; 
          }),
          ...likelihoodDatasets.map(function(ds, i) { 
            return { ...ds, data: [0, ds.data[0], 0] }; 
          }),
          ...criticalityDatasets.map(function(ds, i) { 
            return { ...ds, data: [0, 0, ds.data[0]] }; 
          })
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        scales: {
          x: {
            stacked: true,
            beginAtZero: true,
            ticks: {
              stepSize: 1
            }
          },
          y: {
            stacked: true
          }
        },
        plugins: {
          legend: {
            display: false 
          },
          tooltip: {
            callbacks: {
              label: function(context) {
                return context.dataset.label + ': ' + context.parsed.x;
              }
            }
          }
        }
      }
    });
  }
}

function getColorFromHash(str) {
  var hash = 0;
  for (var i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  var color = (hash & 0x00FFFFFF).toString(16).toUpperCase();
  return '#' + ('00000' + color).slice(-6);
}

function updateZoneAttributes() {
  ['zone-left', 'zone-right', 'zone-reports'].forEach(function(zoneId) {
    var zone = document.getElementById(zoneId);
    if (!zone) return;
    zone.querySelectorAll('.detail-draggable').forEach(function(el) {
      el.setAttribute('data-zone', zoneId);
    });
  });
}


function drawTornadoChart(projectData) {
  var canvas = document.getElementById('tornadoChart-' + projectData.id);
  if (!canvas) return;

  var riskByCrit = {};  
  var oppByCrit = {};

  (projectData.risks || []).forEach(function(r) {
    var label = r.criticalityname || i18n('undefinedValue');
    if (!riskByCrit[label]) riskByCrit[label] = { cost: 0, color: r.criticalitycolor || '#e74c3c' };
    riskByCrit[label].cost += parseFloat(r.impactcost) || 0;
  });

  (projectData.opportunities || []).forEach(function(o) {
    var label = o.criticalityname || i18n('undefinedValue');
    if (!oppByCrit[label]) oppByCrit[label] = { cost: 0, color: o.criticalitycolor || '#2ecc71' };
    oppByCrit[label].cost += parseFloat(o.impactcost) || 0;
  });

  var allLabels = Array.from(new Set(
    Object.keys(riskByCrit).concat(Object.keys(oppByCrit))
  ));

  // Total impact 
  allLabels.sort(function(a, b) {
    var totalA = (riskByCrit[a] ? riskByCrit[a].cost : 0) + (oppByCrit[a] ? oppByCrit[a].cost : 0);
    var totalB = (riskByCrit[b] ? riskByCrit[b].cost : 0) + (oppByCrit[b] ? oppByCrit[b].cost : 0);
    return totalB - totalA;
  });

  // Risks : left /Opportunities right
  var riskValues = allLabels.map(function(l) { return -(riskByCrit[l] ? riskByCrit[l].cost : 0); });
  var oppValues  = allLabels.map(function(l) { return   oppByCrit[l] ? oppByCrit[l].cost : 0; });

  new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: allLabels,
      datasets: [
        {
          label: i18n('menuRisk'),
          data: riskValues,
          backgroundColor: 'rgba(231,76,60,0.75)',
          borderColor: 'rgba(231,76,60,1)',
          borderWidth: 1,
          borderRadius: 4
        },
        {
          label: i18n('menuOpportunity'),
          data: oppValues,
          backgroundColor: 'rgba(46,204,113,0.75)',
          borderColor: 'rgba(46,204,113,1)',
          borderWidth: 1,
          borderRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      scales: {
        x: {
          stacked: false,
          ticks: {
            callback: function(value) {
              return costFormatterText(Math.abs(value));
            }
          },
          grid: { color: 'rgba(0,0,0,0.05)' }
        },
        y: {
          stacked: false,
          ticks: { font: { size: 11 } }
        }
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { font: { size: 11 }, padding: 12 }
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return ctx.dataset.label + ': ' + costFormatterText(Math.abs(ctx.parsed.x));
            }
          }
        }
      }
    }
  });
}

function costFormatterText(value) {
  var html = costFormatter(value, null, false, true);
  var tmp = document.createElement('div');
  tmp.innerHTML = html;
  return tmp.textContent || tmp.innerText || String(value);
}

function loadWorkCommands(projectId, commandId) {
  var tableBody = document.getElementById('workCommandsTable-' + projectId);
  if (!tableBody) return;
  if (!commandId) {
    tableBody.innerHTML = '<tr><td colspan="9" style="padding:15px;text-align:center;color:#999;">' + i18n('selectCommand') + '</td></tr>';
    return;
  } 
  var projectData = window.currentProjectData;
  if (!projectData.commands) {
    tableBody.innerHTML = '<tr><td colspan="9" style="padding:15px;text-align:center;color:#999;">' + i18n('noOrderAvailable') + '</td></tr>';
    return;
  }
  var selectedCommand = projectData.commands.find(function(cmd) { return cmd.id == commandId; });
  if (!selectedCommand || !selectedCommand.workcommands || selectedCommand.workcommands.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="9" style="padding:15px;text-align:center;color:#999;">' + i18n('noWorkCommandAvailable') + '</td></tr>';
    return;
  }
  var html = '';
  selectedCommand.workcommands.forEach(function(wc) {
    html += '<tr style="border-bottom:1px solid #f1f1f1;background:#fff;">';   
    //  1 : Name
    html += '  <td style="padding:12px;color:#4b5563;font-size:13px;">';
    html += htmlEncode(wc.name);
    html += '<br><span style="color:#999;font-size:11px;">' + (wc.nameworkunit || '--') + ' - ' + (wc.namecomplexity || '--') + '</span>';
    html += '</td>';    
    // 2 : Ordered (Qty + Amount)
    html += '  <td style="padding:12px;text-align:center;color:#6b7280;font-size:13px;border-right:1px solid #f1f1f1;">' + numericFormatter(wc.commandquantity) + '</td>';
    html += '  <td style="padding:12px;text-align:right;color:#6b7280;font-size:13px;border-right:1px solid #f1f1f1;">' + costFormatter(wc.commandamount, null, false, true) + '</td>';    
    // 3 : Realised (Qty + Amount)
    html += '  <td style="padding:12px;text-align:center;color:#6b7280;font-size:13px;border-right:1px solid #f1f1f1;">' + numericFormatter(wc.donequantity) + '</td>';
    html += '  <td style="padding:12px;text-align:right;color:#6b7280;font-size:13px;border-right:1px solid #f1f1f1;">' + costFormatter(wc.doneamount, null, false, true) + '</td>';  
    //  4 : Accepted (Qty + Amount)
    html += '  <td style="padding:12px;text-align:center;color:#6b7280;font-size:13px;border-right:1px solid #f1f1f1;">' + numericFormatter(wc.acceptedquantity) + '</td>';
    html += '  <td style="padding:12px;text-align:right;color:#6b7280;font-size:13px;border-right:1px solid #f1f1f1;">' + costFormatter(wc.acceptedamount, null, false, true) + '</td>';  
    //  5 : Billed (Qty + Amount)
    html += '  <td style="padding:12px;text-align:center;color:#6b7280;font-size:13px;border-right:1px solid #f1f1f1;">' + numericFormatter(wc.billedquantity) + '</td>';
    html += '  <td style="padding:12px;text-align:right;color:#6b7280;font-size:13px;">' + costFormatter(wc.billedamount, null, false, true) + '</td>';   
    html += '</tr>';
  });
  tableBody.innerHTML = html;
}

function buildRiskOpportunityBlock(projectData, type,isVisible) {
  // type = 'risk' OR 'opportunity'
  var display = isVisible ? 'block' : 'none';
  var isRisk       = (type === 'risk');
  var items        = isRisk ? (projectData.risks || []) : (projectData.opportunities || []);
  var blockClass   = isRisk ? 'detail-risk-block' : 'detail-opportunity-block';
  var titleKey     = isRisk ? 'menuRisk' : 'menuOpportunity';
  var typeKey      = isRisk ? 'RiskType' : 'OpportunityType';
  var gotoClass    = isRisk ? 'Risk' : 'OpportunityMain';
  var pieCanvasId  = isRisk ? ('riskType-' + projectData.id) : ('oppType-' + projectData.id);
  var barCanvasId = isRisk ? ('riskIndicators-' + projectData.id) : ('oppIndicators-' + projectData.id);
  var nameLabel    = isRisk ? i18n('Risk') : i18n('Opportunity');

  var html = '';
  html += '<div class="' + blockClass + ' detail-draggable" draggable="true" data-section="' + (isRisk ? 'riskDetail' : 'opportunityDetail') + '" ';
  html += 'style="background:white;border-radius:8px;padding:20px;min-width:0;overflow:hidden;display:' + display + ';">';

  html += buildBlockHeader(titleKey);
  
  if (items.length > 0) {
    // Graphs
    html += '  <div style="display:flex;gap:20px;align-items:stretch;min-height:250px;padding:15px 0 0 0;">';
    // Pie type
    html += '    <div style="flex:0 0 30%;display:flex;flex-direction:column;align-items:center;justify-content:center;border-right:1px solid #e0e0e0;padding-right:20px;">';
    html += '      <div style="font-size:12px;font-weight:600;color:#666;margin-bottom:10px;">' + i18n(typeKey) + '</div>';
    html += '      <div style="width:100%;height:250px;position:relative;">';
    html += '        <canvas id="' + pieCanvasId + '" style="max-width:100%;"></canvas>';
    html += '      </div>';
    html += '    </div>';
    // Bar 
    html += '    <div style="flex:1;display:flex;flex-direction:column;justify-content:center;min-width:0;">';
	html += '    <div style="flex:1;display:flex;flex-direction:column;justify-content:center;min-width:0;">';
	html += '      <div style="font-size:12px;font-weight:600;color:#666;margin-bottom:10px;">' + i18n('breakdownByIndicator') + '</div>';
	html += '      <div style="height:250px;position:relative;">';
	html += '        <canvas id="' + barCanvasId + '" style="max-width:100%;"></canvas>';
	html += '      </div>';
	html += '    </div>';
    html += '    </div>';
    html += '  </div>';
  }

  // Table
  html += '  <div style="margin-top:' + (items.length > 0 ? '24' : '0') + 'px;">';
  html += '    <div style="border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;background:#fff;box-shadow:0 4px 20px rgba(0,0,0,0.04);">';
  html += '      <div style="overflow-x:auto;">';
  html += '        <table style="width:100%;border-collapse:separate;border-spacing:0;font-family:Inter,sans-serif;">';
  // Header
  html += '          <thead><tr style="background:#f9fafb;">';
  var headers = [
    { label: nameLabel, style: 'width:180px;max-width:180px;' },
    { label: i18n('dashboardTicketMainTitleType'),  style: 'width:150px;max-width:150px;' },
    { label: i18n('colIdSeverity'), style: '' },
    { label: i18n('colIdLikelihood'), style: '' },
    { label: i18n('colIdCriticality'), style: '' },
    { label: i18n('colImpactCost'), style: 'text-align:right;' },
    { label: i18n('colProjectReserveAmount'), style: 'text-align:right;' },
    { label: i18n('colStatus'), style: '' },
  ];
  headers.forEach(function(h) {
    html += '<th style="padding:12px 14px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;' + h.style + '">';
    html += h.label.charAt(0).toUpperCase() + h.label.slice(1);
    html += '</th>';
  });
  html += '          </tr></thead>';
  // Body
  html += '          <tbody>';
  if (items.length > 0) {
    items.forEach(function(item) {
      var typeValue = isRisk ? (item.risktype || '-') : (item.opportunitytype || '-');
      html += '<tr onclick="gotoElement(\'' + gotoClass + '\', \'' + item.id + '\')" ';
      html += 'style="cursor:pointer;transition:all .15s ease;border-bottom:1px solid #f3f4f6;" ';
      html += 'onmouseover="this.style.background=\'#f9fafb\'" onmouseout="this.style.background=\'white\'">';
      // Nom + statut
      html += '<td style="padding:11px 14px;">';
      html += '  <div style="display:flex;align-items:center;gap:10px;">';
      html += '    <div style="width:9px;height:9px;border-radius:999px;flex-shrink:0;background:' + item.colorstatus + ';box-shadow:0 0 0 1px rgba(0,0,0,0.18);"></div>';
      html += '    <div style="font-size:13px;font-weight:600;color:#374151;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px;" title="' + htmlEncode(item.name || '') + '">';
      html +=        (item.name || '-');
      html += '    </div>';
      html += '  </div>';
      html += '</td>';
      // Type
      html += '<td style="padding:11px 14px;font-size:13px;color:#6b7280;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:150px;" title="' + htmlEncode(typeValue) + '">';
      html +=    typeValue;
      html += '</td>';
      // Severity / Likelihood / Criticality 
      ['severity', 'likelihood', 'criticality'].forEach(function(indicator) {
        html += '<td style="padding:11px 14px;">';
        html += '  <div style="display:inline-flex;align-items:center;gap:8px;">';
        html += '    <div style="width:10px;height:10px;border-radius:3px;background:' + (item[indicator + 'color'] || '#ccc') + ';"></div>';
        html += '    <span style="font-size:13px;color:#6b7280;white-space:nowrap;">' + (item[indicator + 'name'] || '-') + '</span>';
        html += '  </div>';
        html += '</td>';
      });
      // Impact cost
      html += '<td style="padding:11px 14px;text-align:right;font-size:13px;color:#6b7280;white-space:nowrap;">';
      html +=    (item.impactcost ? costFormatter(item.impactcost, null, false, true) : '-');
      html += '</td>';
      // Reserve amount
      html += '<td style="padding:11px 14px;text-align:right;font-size:13px;color:#6b7280;white-space:nowrap;">';
      html +=    (item.projectreserveamount ? costFormatter(item.projectreserveamount, null, false, true) : '-');
      html += '</td>';
      // Statut badge
      html += '<td style="padding:11px 14px;">';
      html += '  <div style="display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;';
      html += '              background:' + item.colorstatus + ';color:' + getForeColor(item.colorstatus) + ';';
      html += '              font-size:11px;font-weight:600;white-space:nowrap;box-shadow:0 0 0 1px rgba(0,0,0,0.18);">';
      html +=    item.status;
      html += '  </div>';
      html += '</td>';
      html += '</tr>';
    });
  } else {
    html += '<tr><td colspan="8" style="padding:56px 24px;text-align:center;color:#9ca3af;font-size:13px;">' + i18n('noDataFound') + '</td></tr>';
  }
  html += '          </tbody>';
  html += '        </table>';
  html += '      </div>';
  html += '    </div>';
  html += '  </div>';
  html += '</div>'; // fin bloc

  return html;
}

function drawIndicatorCharts(projectData, type) {
  var isRisk = (type === 'risk');
  var items = isRisk ? projectData.risks : projectData.opportunities;
  var pieId = isRisk ? 'riskType-'+ projectData.id : 'oppType-' + projectData.id;
  var barId = isRisk ? 'riskIndicators-' + projectData.id : 'oppIndicators-' + projectData.id;
  var typeField = isRisk ? 'risktype' : 'opportunitytype';

  // Pie
  var pieCanvas = document.getElementById(pieId);
  if (pieCanvas) {
    var typeCount = {}, typeColors = {};
    items.forEach(function(item) {
      var t = item[typeField] || i18n('undefinedValue');
      typeCount[t]  = (typeCount[t] || 0) + 1;
      typeColors[t] = typeColors[t] || getColorFromHash(t + type);
    });
    var labels = Object.keys(typeCount);
    var data   = labels.map(function(l) { return typeCount[l]; });
    var colors = labels.map(function(l) { return typeColors[l]; });
    new Chart(pieCanvas.getContext('2d'), {
      type: 'doughnut',
      data: { labels: labels, datasets: [{ data: data, backgroundColor: colors, borderColor: '#fff', borderWidth: data.length === 1 ? 0 : 2 }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 10 } },
          tooltip: { callbacks: { label: function(ctx) { return ctx.label + ': ' + ctx.parsed; } } }
        },
        cutout: data.length === 1 ? '0%' : '50%'
      }
    });
  }

  // Bar breakdown severity/likelihood/criticality
  var barCanvas = document.getElementById(barId);
  if (barCanvas) {
    var buckets = { severity: {}, likelihood: {}, criticality: {} };
    items.forEach(function(item) {
      ['severity','likelihood','criticality'].forEach(function(ind) {
        var n = item[ind + 'name'] || i18n('undefinedValue');
        buckets[ind][n] = buckets[ind][n] || { count: 0, color: item[ind + 'color'] || '#999' };
        buckets[ind][n].count++;
      });
    });
    var datasets = [];
    var axisLabels = [i18n('colIdSeverity'), i18n('colIdLikelihood'), i18n('colIdCriticality')];
    ['severity','likelihood','criticality'].forEach(function(ind, idx) {
      Object.keys(buckets[ind]).forEach(function(name) {
        var d = [0, 0, 0];
        d[idx] = buckets[ind][name].count;
        datasets.push({ label: name, data: d, backgroundColor: buckets[ind][name].color });
      });
    });
    new Chart(barCanvas.getContext('2d'), {
      type: 'bar',
      data: { labels: axisLabels, datasets: datasets },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        scales: {
          x: { stacked: true, beginAtZero: true, ticks: { stepSize: 1 } },
          y: { stacked: true }
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: function(ctx) { return ctx.dataset.label + ': ' + ctx.parsed.x; } } }
        }
      }
    });
  }
}


function buildTornadoBlock(projectData, isVisible) {
  var display = isVisible ? 'block' : 'none';
  var hasData  = (projectData.risks && projectData.risks.length > 0) ||
                 (projectData.opportunities && projectData.opportunities.length > 0);

  var html = '';
  html += '<div class="detail-tornado-block detail-draggable" draggable="true" data-section="tornadoDetail" ';
  html += 'style="background:white;border-radius:8px;padding:20px;min-width:0;overflow:hidden;display:' + display + ';">';

  html += '  <div style="display:flex;align-items:center;gap:8px;margin-bottom:15px;">';
  html += '    <div class="drag-handle" style="cursor:grab;color:#d1d5db;padding:2px 4px;border-radius:4px;font-size:16px;line-height:1;user-select:none;">⠿</div>';
  html += '    <div style="font-size:14px;font-weight:600;color:var(--color-dark);">' + i18n('tornadoChartRiskVsOpportunity') + '</div>';
  html += '  </div>';
  html += '  <div style="border-top:1px solid #e0e0e0;margin-bottom:16px;"></div>';

  if (hasData) {
    html += '  <div style="height:300px;position:relative;">';
    html += '    <canvas id="tornadoChart-' + projectData.id + '" style="max-width:100%;"></canvas>';
    html += '  </div>';
  } else {
    html += '  <div style="padding:40px;text-align:center;color:#9ca3af;font-size:13px;">' + i18n('noDataFound') + '</div>';
  }

  html += '</div>';
  return html;
}

function loadBurndownChart(projectId) {
  var container = document.getElementById('burndown-chart-' + projectId);
  if (!container) return;
  var params = new URLSearchParams({
    idProject: projectId,
    format: 'day',
    showBurndownToday: '1',
  });
  var reportUrl = '../report/burndownChart.php?' + params.toString(); 
  // Create an iframe to load the report independently
  var iframe = document.createElement('iframe');
  iframe.style.cssText = 'width:100%;height:700px;border:none;zoom:0.75;';
  iframe.src = reportUrl; 
  container.innerHTML = '';
  container.appendChild(iframe);  
  iframe.onerror = function() {
    container.innerHTML = '<div style="text-align:center;color:#999;padding:40px;">' + i18n('errorLoadingReport') + '</div>';
  };
}

function loadFortyFiveDegreeChart(projectId) {
  var container = document.getElementById('fortyFiveDegree-chart-' + projectId);
  if (!container) return;
  var params = new URLSearchParams({
    idProject: projectId,
    format: 'day',
    showBurndownToday: '1',
  });
  var reportUrl = '../report/report45DegreeChart.php?' + params.toString(); 
  // Create an iframe to load the report
  var iframe = document.createElement('iframe');
  iframe.style.cssText = 'width:100%;height:700px;border:none;zoom:0.75;';
  iframe.src = reportUrl;
  container.innerHTML = '';
  container.appendChild(iframe);
  iframe.onerror = function() {
    container.innerHTML = '<div style="text-align:center;color:#999;padding:40px;">' + i18n('errorLoadingReport') + '</div>';
  };
}

function loadSCurveChart(projectId,idBaseline) {
	var container = document.getElementById('sCurve-chart-' + projectId);
	if (!container) return;  
	var params = new URLSearchParams({
	  idProject: projectId,
	  format: 'day',
	  showBurndownToday: '1',
	  idBaselineSelect: idBaseline,
	});
	var reportUrl = '../report/reportSCurveChart.php?' + params.toString(); 
	// Create an iframe to load the report
	var iframe = document.createElement('iframe');
	iframe.style.cssText = 'width:100%;height:700px;border:none;zoom:0.75;';
	iframe.src = reportUrl;
	container.innerHTML = '';
	container.appendChild(iframe);
	iframe.onerror = function() {
	  container.innerHTML = '<div style="text-align:center;color:#999;padding:40px;">' + i18n('errorLoadingReport') + '</div>';
	};
}

function buildBlockHeader(titleKey) {
  var html = '';
  html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:15px;">';
  html += '  <div class="drag-handle" title="' + i18n('dragToReorder') + '" ';
  html += '       style="cursor:grab;color:#d1d5db;padding:2px 4px;border-radius:4px;font-size:16px;line-height:1;user-select:none;">⠿</div>';
  html += '  <div style="font-size:14px;font-weight:600;color:var(--color-dark);">' + i18n(titleKey) + '</div>';
  html += '</div>';
  html += '<div style="border-top:1px solid #e0e0e0;margin-bottom:12px;"></div>';
  return html;
}

function toggleAttachmentPopover(projectId) {
  var popover = document.getElementById('attPopover-' + projectId);
  if (!popover) return;
  var isVisible = popover.style.display !== 'none';
  document.querySelectorAll('[id^="attPopover-"]').forEach(function(p) {
    p.style.display = 'none';
  });

  if (!isVisible) {
    popover.style.display = 'block';
    setTimeout(function() {
      document.addEventListener('click', function closePopover(e) {
        var container = document.getElementById('attContainer-' + projectId);
        if (container && !container.contains(e.target)) {
          popover.style.display = 'none';
          document.removeEventListener('click', closePopover);
        }
      });
    }, 0);
  }
}

function getDetailParameter(paramName) {
  var switchWidget = dijit.byId(paramName);
  if (switchWidget) {
    return switchWidget.get('value') === 'on';
  }
  return false;
}

function toggleDashboardParameterDetail(paramName) {
  var switchWidget = dijit.byId(paramName);
  if (switchWidget) {
    var currentValue = switchWidget.get('value');
    var newValue = (currentValue === 'on') ? 'off' : 'on';
    switchWidget.set('value', newValue);
  }
}

function enhancedSwitchHandlerDetail(paramName, newValue, completeRefresh) {
  if (completeRefresh === undefined) completeRefresh = false;
  
  var isVisible = (newValue === 'on');
  saveDataToSession(paramName, newValue, true);
  
  if (completeRefresh) {
    var projectId = dojo.byId('currentProjectId').value;
    if (projectId) {
      loadContent("projectDashboardDetailMain.php?idProject=" + projectId, "centerDiv");
    }
  } else {
    applyDetailParameterVisibility(paramName, isVisible);
  }
}

function applyDetailParameterVisibility(paramName, isVisible) {
  var displayValue = isVisible ? 'block' : 'none';
  
  switch(paramName) {
    case 'objectivesDetail':
      var objectivesBlocks = document.querySelectorAll('.detail-objectives-block');
      objectivesBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'weatherDetail':
      var weatherBlocks = document.querySelectorAll('.detail-weather-block');
      weatherBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'resourceDetail':
      var resourceBlocks = document.querySelectorAll('.detail-resource-block');
      resourceBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'milestoneDetail':
      var milestoneBlocks = document.querySelectorAll('.detail-milestone-block');
      milestoneBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
	  if (isVisible) refreshTimelineIfNeeded();
      break;
      
    case 'financialDetail':
      var financialBlocks = document.querySelectorAll('.detail-financial-block');
      financialBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'budgetDetail':
      var budgetBlocks = document.querySelectorAll('.detail-budget-block');
      budgetBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'revenueDetail':
      var revenueBlocks = document.querySelectorAll('.detail-revenue-block');
      revenueBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'riskDetail':
      var riskBlocks = document.querySelectorAll('.detail-risk-block');
      riskBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
	  
	case 'opportunityDetail':
	  var opportunityBlocks = document.querySelectorAll('.detail-opportunity-block');
	  opportunityBlocks.forEach(function(elem) {
	    elem.style.display = displayValue;
	   });
	   break;
	   
	case 'tornadoDetail':
	   document.querySelectorAll('.detail-tornado-block').forEach(function(elem) {
	     elem.style.display = displayValue;
	   });
	   break;
	   
	case 'raciDetail':
	   document.querySelectorAll('.detail-raci-block').forEach(function(elem) {
	     elem.style.display = displayValue;
	   });
	   break;
      
    case 'burndownDetail':
      var burndownBlocks = document.querySelectorAll('.detail-burndown-block');
      burndownBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'fortyFiveDegreeDetail':
      var fortyFiveBlocks = document.querySelectorAll('.detail-45degree-block');
      fortyFiveBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
      
    case 'sCurveDetail':
      var sCurveBlocks = document.querySelectorAll('.detail-scurve-block');
      sCurveBlocks.forEach(function(elem) {
        elem.style.display = displayValue;
      });
      break;
  }
}

function saveLayoutRecordingDetail() {
  var layoutSelect = dijit.byId('layoutRecordingDetail');
  if (!layoutSelect) {
    showAlert(i18n('pleaseSelectLayout'));
    return;
  }
  var selectedLayout = layoutSelect.get('value');
  if (!selectedLayout) {
    showAlert(i18n('pleaseSelectLayout'));
    return;
  }

  var parametersToSave = [
    'objectivesDetail', 
	'weatherDetail', 
	'resourceDetail',
    'milestoneDetail', 
	'financialDetail', 
	'budgetDetail',
	'revenueDetail', 
	'riskDetail', 
	'opportunityDetail',
	'tornadoDetail',
	'raciDetail',
	'burndownDetail', 
	'fortyFiveDegreeDetail', 
	'sCurveDetail'
  ];

  var paramValues = {};
  parametersToSave.forEach(function(paramName) {
    var widget = dijit.byId(paramName);
    if (widget) paramValues[paramName] = widget.get('value');
  });

  var sectionOrder = {};
  ['zone-left', 'zone-right', 'zone-reports'].forEach(function(zoneId) {
    var zone = document.getElementById(zoneId);
    if (!zone) return;
    sectionOrder[zoneId] = Array.from(
      zone.querySelectorAll('.detail-draggable[data-section]')
    ).map(function(el) { return el.getAttribute('data-section'); });
  });
  paramValues['_sectionOrder'] = sectionOrder;

  var sessionKey = 'paramLayoutDetail_' + selectedLayout;
  saveDataToSession(sessionKey, JSON.stringify(paramValues), true);
  showAlert(i18n('layoutSavedSuccessfully'));
}

function restoreLayoutRecordingDetail(layoutName) {
  if (!layoutName || layoutName === '' || layoutName === ' ') return;

  var sessionKey = 'paramLayoutDetail_' + layoutName;
  dojo.xhrGet({
    url: "../tool/getParamDashboard.php?key=" + sessionKey + addTokenIndexToUrl(),
    handleAs: "text",
    load: function(data) {
      try {
        if (!data || data === '' || data === 'null') {
          showAlert(i18n('noParamSaved'));
          return;
        }
        var params = JSON.parse(data);

        for (var paramName in params) {
          if (paramName === '_sectionOrder') continue;
          if (params.hasOwnProperty(paramName)) {
            var value = params[paramName];
            var widget = dijit.byId(paramName);
            if (widget) {
              widget.set('value', value);
              saveDataToSession(paramName, value, true);
              applyDetailParameterVisibility(paramName, value === 'on');
            }
          }
        }

        if (params['_sectionOrder']) {
          var order = params['_sectionOrder'];
          ['zone-left', 'zone-right', 'zone-reports'].forEach(function(zoneId) {
            var zone = document.getElementById(zoneId);
            if (!zone || !order[zoneId]) return;
            order[zoneId].forEach(function(sectionName) {
              if (!sectionName) return;
              var el = document.querySelector('[data-section="' + sectionName + '"]');
              if (el) zone.appendChild(el);
            });
          });
          saveDataToSession('sectionOrderDetail', JSON.stringify(order), true);
        }

      } catch(e) {
        console.error(e);
      }
    }
  });
}

function initializeLayoutRecordingDetail() {
  var addRecordingButton = dojo.byId('addRecordingDashboardDetail');
  if (addRecordingButton) {
    dojo.connect(addRecordingButton, 'onclick', function(evt) {
      saveLayoutRecordingDetail();
    });
  }
}

function onSearchByLayoutChangeDetail(newLayout) {
  saveDataToSession('searchByLayoutDetail', newLayout, false);
  restoreLayoutRecordingDetail(newLayout);
}

function refreshTimelineIfNeeded() {
  var projectData = window.currentProjectData;
  if (!projectData) return;

  var timelineCanvas = document.getElementById('timeline-detail-' + projectData.id);
  if (!timelineCanvas) return;

  timelineCanvas.width  = 0;
  timelineCanvas.height = 0;
  setTimeout(function() {
    var useColorMilestone = getDashboardParameter('colorMilestone');
    createTimeline('timeline-detail-' + projectData.id,projectData.validatedstartdate,projectData.plannedstartdate,projectData.realstartdate,projectData.validatedenddate,projectData.plannedenddate,projectData.realenddate,projectData.milestones || [],useColorMilestone,getTimelineDateValues(projectData));
  }, 50);
}

function initDragAndDrop() {
  var draggables = document.querySelectorAll('.detail-draggable');
  var dropZones = document.querySelectorAll('.detail-drop-zone');
  var dragSrc = null;
  var placeholder = null;

  draggables.forEach(function(el) {

    el.addEventListener('dragstart', function(e) {
      dragSrc = el;
      el.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', el.getAttribute('data-section'));
    });

    el.addEventListener('dragend', function() {
      el.classList.remove('dragging');
      dragSrc = null;
      if (placeholder && placeholder.parentNode) {
        placeholder.parentNode.removeChild(placeholder);
      }
      placeholder = null;
      dropZones.forEach(function(z) { z.classList.remove('drag-over'); });
      saveSectionOrder();
	  updateZoneAttributes();
	  refreshTimelineIfNeeded();
    });
  });

  dropZones.forEach(function(zone) {

    zone.addEventListener('dragover', function(e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      zone.classList.add('drag-over');

      var afterEl = getDragAfterElement(zone, e.clientY);

      if (!placeholder) {
        placeholder = document.createElement('div');
        placeholder.className = 'detail-drop-placeholder';
      }

      if (afterEl) {
        zone.insertBefore(placeholder, afterEl);
      } else {
        zone.appendChild(placeholder);
      }
    });

    zone.addEventListener('dragleave', function(e) {
      if (!zone.contains(e.relatedTarget)) {
        zone.classList.remove('drag-over');
        if (placeholder && placeholder.parentNode === zone) {
          zone.removeChild(placeholder);
        }
      }
    });

    zone.addEventListener('drop', function(e) {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (!dragSrc) return;

      var afterEl = getDragAfterElement(zone, e.clientY);
      if (placeholder && placeholder.parentNode) {
        placeholder.parentNode.removeChild(placeholder);
      }

      if (afterEl) {
        zone.insertBefore(dragSrc, afterEl);
      } else {
        zone.appendChild(dragSrc);
      }
    });
  });
}

function getDragAfterElement(zone, y) {
  var draggables = Array.from(
    zone.querySelectorAll('.detail-draggable:not(.dragging)')
  );

  return draggables.reduce(function(closest, child) {
    var box = child.getBoundingClientRect();
    var offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) {
      return { offset: offset, element: child };
    }
    return closest;
  }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function saveSectionOrder() {
  var order = {};
  ['zone-left', 'zone-right', 'zone-reports'].forEach(function(zoneId) {
    var zone = document.getElementById(zoneId);
    if (!zone) return;
    var sections = Array.from(zone.querySelectorAll('.detail-draggable[data-section]'));
    order[zoneId] = sections.map(function(el) {
      return el.getAttribute('data-section');
    });
  });
  var json = JSON.stringify(order);
  saveDataToSession('sectionOrderDetail', json, true);
}

function restoreSectionOrder() {
  var url = "../tool/getParamDashboard.php?key=sectionOrderDetail" + addTokenIndexToUrl();
  dojo.xhrGet({
    url: url,
    handleAs: "text",
    load: function(data) {
      if (!data || data === 'null' || data === '') return;
      try {
        var order = JSON.parse(data);
        // Search for each element in the ENTIRE DOM, not just within its area
        ['zone-left', 'zone-right', 'zone-reports'].forEach(function(zoneId) {
          var zone = document.getElementById(zoneId);
          if (!zone || !order[zoneId]) return;
          order[zoneId].forEach(function(sectionName) {
            if (!sectionName) return;
            // global `querySelector` on the document, not on a zone
            var el = document.querySelector('[data-section="' + sectionName + '"]');
            if (el) zone.appendChild(el);
          });
        });
      } catch(e) {
        console.warn('Could not restore section order:', e);
      }
    }
  });
}
