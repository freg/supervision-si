<?php
/*
 *	@author: qCazelles 
 */

require_once('_securityCheck.php');
class WorkCommandAccepted extends SqlElement {
	
	public $id;
	public $idCommand;
	public $idWorkCommand;
	public $refType;
	public $refId;
	public $acceptedQuantity;
	public $idActivityWorkUnit;
	public $idAcceptance;
	public $acceptedDate;
	
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
	
	public function save() {
	  $result=parent::save();
	  $wc = new WorkCommand($this->idWorkCommand);
	  $wc->updateAcceptedCommand();
	  return $result;
	}
	
	public function delete(){
	  $this->acceptedDate = null;
	  $result = parent::delete();
	  $wc = new WorkCommand($this->idWorkCommand);
	  $wc->updateAcceptedCommand();
	  return $result;
	}
	
}