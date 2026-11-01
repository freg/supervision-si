<?php
/*
 *	@author: qCazelles 
 */

require_once('_securityCheck.php');
class LockedImputation extends SqlElement {
	
	// extends SqlElement, so has $id
	public $_sec_Description;
	public $id;    // redefine $id to specify its visible place
	public $idProject;
	public $idResource;
	public $month;
	public $_isNameTranslatable = true;
	//public $_sec_void;
	
	private static $_databaseCriteria = array();
	/** ==========================================================================
	 * Constructor
	 * @param $id Int the id of the object in the database (null if not stored yet)
	 * @return void
	 */
	
	/** ========================================================================
	 * Return the specific database criteria
	 * @return String the databaseTableName
	 */
	protected function getStaticDatabaseCriteria() {
	  return self::$_databaseCriteria;
	}
	
	/** ==========================================================================
	 * Construct
	 * @return void
	 */
	function __construct($id = NULL, $withoutDependentObjects=false) {
		parent::__construct($id,$withoutDependentObjects);
	}
	
	
	/** ==========================================================================
	 * Destructor
	 * @return void
	 */
	function __destruct() {
		parent::__destruct();
	}
	
	public static function isLockedPeriodForProject($curDate, $idProject) {
	  
	  $month=pq_substr($curDate,0,4).pq_substr($curDate,5,2);
	  
	  $locked= new LockedImputation();
	  $clause="idProject=".Sql::fmtId($idProject)." and month < '$month' ";
	  $lockedProj=$locked->countSqlElementsFromCriteria(null,$clause);
	  if($lockedProj>0){
      return 'locked';
	  }	    
	  
	  $consolidated= new ConsolidationValidation();
	  $clause="idProject=".Sql::fmtId($idProject)." and month = '$month' ";
	  $consolidatedProj=$consolidated->countSqlElementsFromCriteria(null,$clause);
	  if($consolidatedProj>0) {
	    return 'consolidated';
	  }
	  return false;
	  
	}
	
	
}